"""The engine's operators: scan, filter and project, each pulling batches from the one below (ch01).

A plan is a tree of operators. Each operator has one job and one output: a stream of Arrow
record batches, produced by :meth:`Operator.batches`. An operator gets its input by asking its
child for batches, one at a time, so the operator at the top of the plan drives the whole run:
nothing is read until something above asks for it. That is the pull model, the one most engines
use. The arrays in each batch are built buffer by buffer, by :mod:`query_lab.memory` (ch02).

Every operator counts what it does in a :class:`~query_lab.metrics.Metrics` as it runs, as
COUNTERS.md defines. The counts are exact, so the book can print them and a test can compare
them with DuckDB's.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
from parquet_lab import page_index, prune, stats
from parquet_lab.bytes import Span
from parquet_lab.column import read_column, read_column_pages
from parquet_lab.metadata import FileMetaData, RowGroup
from parquet_lab.object_store import All, Bounded, MemoryStore, NetworkModel, TracingStore
from parquet_lab.reader import FooterOptions, read_footer
from parquet_lab.scan import Fetched
from parquet_lab.schema import Leaf, build, leaves

from .memory import array_from
from .metrics import Metrics

#: A predicate or an expression: a function of a batch that returns one Arrow array, one value
#: per row of the batch. The engine's kernels are pyarrow.compute's.
BatchFunction = Callable[[pa.RecordBatch], pa.Array]


class Operator:
    """One step of a plan. Subclasses produce batches and count what they did."""

    def __init__(self, name: str, detail: str, children: list[Operator]) -> None:
        self.children = children
        self.metrics = Metrics(name, detail, children=[c.metrics for c in children])

    def batches(self) -> Iterator[pa.RecordBatch]:
        raise NotImplementedError

    def run(self) -> pa.Table:
        """Pull every batch through the plan and collect the result."""
        return pa.Table.from_batches(list(self.batches()), schema=self.schema())

    def schema(self) -> pa.Schema:
        raise NotImplementedError

    def emit(self, batch: pa.RecordBatch) -> pa.RecordBatch:
        """Count a batch on its way out. Every operator hands its output through here."""
        self.metrics.rows_out += batch.num_rows
        self.metrics.batches_out += 1
        # A streaming operator holds one batch at a time: its largest is its peak.
        self.metrics.peak_memory_bytes = max(self.metrics.peak_memory_bytes, batch.get_total_buffer_size())
        return batch

    def take(self, batch: pa.RecordBatch) -> pa.RecordBatch:
        """Count a batch on its way in, from a child."""
        self.metrics.rows_in += batch.num_rows
        self.metrics.batches_in += 1
        return batch


@dataclass(frozen=True)
class Comparison:
    """A predicate a scan can test by itself: one column compared with a constant (ch03).

    The scan uses it twice. Before it reads a row group, it asks the row group's statistics
    whether any value in it could satisfy the comparison, and skips the row group if none could.
    After it reads one, it tests every row.
    """

    column: str
    op: str
    """One of ``=``, ``!=``, ``<``, ``<=``, ``>``, ``>=``."""
    value: object
    """A constant of the column's type: an int, a float, a str or a date."""

    def __str__(self) -> str:
        return f"{self.column} {self.op} {self.value}"

    def mask(self, batch: pa.RecordBatch) -> pa.Array:
        """True for each row of ``batch`` that satisfies the comparison."""
        column = batch[self.column]
        return KERNELS[self.op](column, pa.scalar(self.value, column.type))

    def against_statistics(self, leaf: Leaf, metadata: FileMetaData, row_group: RowGroup) -> prune.Decision:
        """Whether ``row_group`` can be skipped, from its statistics for the column, and why.

        The Parquet book's reader decides: it reads the chunk's minimum and maximum, and asks
        whether any value between them could satisfy the comparison.
        """
        chunk = row_group.columns[leaf.column]
        if chunk.statistics is None:
            return prune.read("the column chunk has no statistics")
        converted = metadata.schema[leaf.element].converted_type
        predicate = prune.Predicate.new(leaf, converted, prune.Op(self.op), _literal(self.value))
        orders = metadata.column_orders
        type_order = orders is not None and orders[leaf.column] == "TYPE_ORDER"
        try:
            bounds = stats.bounds(chunk.statistics, predicate.comparator, type_order)
            found = (bounds.min, bounds.max)
        except ValueError:
            found = None
        return prune.against_bounds(predicate, found, chunk.statistics.null_count, chunk.num_values)

    def against_page(
        self, leaf: Leaf, metadata: FileMetaData, index: page_index.ColumnIndex, page: int, rows: int
    ) -> prune.Decision:
        """Whether one page can be skipped, from the column index's bounds for it (ch04).

        The same question as :meth:`against_statistics`, asked of one page of ``rows`` rows
        instead of a whole row group: the column index keeps a minimum and maximum for each page.
        """
        converted = metadata.schema[leaf.element].converted_type
        predicate = prune.Predicate.new(leaf, converted, prune.Op(self.op), _literal(self.value))
        orders = metadata.column_orders
        type_order = orders is not None and orders[leaf.column] == "TYPE_ORDER"
        if index.null_pages[page]:
            return prune.against_bounds(predicate, None, rows, rows)
        nulls = index.null_counts[page] if index.null_counts is not None else None
        found = (index.min_values[page], index.max_values[page]) if type_order else None
        return prune.against_bounds(predicate, found, nulls, rows)

    def against_bounds(self, comparator: stats.Comparator, lower: bytes, upper: bytes) -> prune.Decision:
        """Whether a whole file can be skipped, from the bounds a table's metadata keeps for it (ch05).

        The metadata stores each column's bounds as the file's statistics store them, PLAIN-encoded,
        with the comparator that orders them, so the Parquet book's reader can decide as it does for
        a row group, before the file is opened.
        """
        value = prune.literal(comparator, _literal(self.value))
        predicate = prune.Predicate(0, prune.Op(self.op), value, comparator)
        return prune.against_bounds(predicate, (lower, upper), None, 1)


#: The kernel that tests each row, for each comparison.
KERNELS = {
    "=": pc.equal,
    "!=": pc.not_equal,
    "<": pc.less,
    "<=": pc.less_equal,
    ">": pc.greater,
    ">=": pc.greater_equal,
}


def _literal(value: object) -> str:
    """A constant as the Parquet book's reader parses one: a date as the days since 1970."""
    if isinstance(value, dt.date):
        return str((value - dt.date(1970, 1, 1)).days)
    return str(value)


class Scan(Operator):
    """Read columns of a Parquet file, one batch per row group, with the Parquet book's reader.

    The file sits in the reader's simulated object store, so every byte the scan reads is a
    request the store logged: the footer first, then each column chunk it needs. With no
    ``filters``, as in ch01, the scan reads every row group and hands up every row. With filters
    (ch03), it skips each row group whose statistics rule out every row, and hands up only the
    rows that pass.
    """

    def __init__(
        self,
        path: str | Path,
        columns: list[str],
        filters: list[Comparison] = (),
        page_index: bool = False,
        store: tuple[TracingStore, str] | None = None,
    ) -> None:
        detail = f"{Path(path).name}: {', '.join(columns)}"
        if filters:
            detail += f"; {' AND '.join(map(str, filters))}"
        if page_index:
            detail += "; by page"
        super().__init__("Scan", detail, [])
        self.path = Path(path)
        self.columns = columns
        self.filters = list(filters)
        self.page_index = page_index
        """Whether to consult each row group's page index and read only the pages it keeps (ch04)."""
        self.store = store
        """A store the scan shares, and the file's key in it: a table's files share one (ch05).
        Without one, the scan puts the file in a store of its own."""
        self.skipped: dict[int, str] = {}
        """Each row group the scan skipped, by its position in the file, with the reason."""
        self.kept: dict[int, list[tuple[int, int]]] = {}
        """Each row group the scan read, with the rows it read of it, as ``[start, end)`` ranges."""

    # Row group by row group: one the statistics rule out is never requested at all.
    def batches(self) -> Iterator[pa.RecordBatch]:
        data = self.path.read_bytes()
        if self.store is None:
            key = self.path.name
            objects = MemoryStore()
            objects.put(key, data)
            store = TracingStore(objects, NetworkModel())
        else:
            store, key = self.store
        before = len(store.requests)
        footer = read_footer(store, key, FooterOptions())
        # The reader decodes only bytes the store returned; anything else reads as zeros.
        have = Fetched(len(data))
        for request in store.requests[before:]:
            if request.returned is not None:
                have.add(request.returned, data[request.returned.start : request.returned.end])
        by_name = {leaf.dotted_path(): leaf for leaf in leaves(build(footer.metadata.schema))}
        # The columns asked for, then any column a filter tests that was not asked for.
        reading = list(dict.fromkeys([*self.columns, *(f.column for f in self.filters)]))
        wanted = [by_name[name] for name in reading]
        schema = pa.schema([arrow_field(leaf) for leaf in wanted])
        self.skipped, self.kept = {}, {}
        self.count_requests(store)
        reader = (store, key, have)

        for index, row_group in enumerate(footer.metadata.row_groups):
            why = self.ruled_out(row_group, footer.metadata, by_name)
            if why is not None:
                self.skipped[index] = why
                continue
            rows = [(0, row_group.num_rows)]
            if self.page_index:
                rows = self.pages_kept(row_group, footer.metadata, by_name, reader)
                if not rows:
                    self.skipped[index] = "the page index rules out every page"
                    continue
            self.kept[index] = rows
            arrays = [self.read(leaf, row_group, rows, reader) for leaf in wanted]
            batch = pa.RecordBatch.from_arrays(arrays, schema=schema)
            self.take(batch)
            # Until it has tested the rows, the scan holds every column it read, the filters' too.
            self.metrics.peak_memory_bytes = max(
                self.metrics.peak_memory_bytes, batch.get_total_buffer_size()
            )
            for f in self.filters:
                batch = batch.filter(f.mask(batch))
            self.count_requests(store)
            yield self.emit(batch.select(self.columns))
        self.count_requests(store)

    def ruled_out(self, row_group: RowGroup, metadata: FileMetaData, by_name: dict[str, Leaf]) -> str | None:
        """Why no row of ``row_group`` can pass the filters, from its statistics, or None if
        some row might. One filter that rules the row group out is enough: they all must pass."""
        for f in self.filters:
            decision = f.against_statistics(by_name[f.column], metadata, row_group)
            if decision.skip:
                return f"{f}: {decision.why}"
        return None

    def count_requests(self, store: TracingStore) -> None:
        self.metrics.bytes_read = store.bytes_returned()
        self.metrics.requests = len(store.requests)

    def pages_kept(
        self, row_group: RowGroup, metadata: FileMetaData, by_name: dict[str, Leaf], reader: tuple
    ) -> list[tuple[int, int]]:
        """The rows of ``row_group`` the page index cannot rule out, as ``[start, end)`` ranges.

        Each filter reads its column's page index and keeps the pages whose bounds might hold a
        match. A row must pass every filter, so it is read only if every filter kept its page.
        """
        kept = [(0, row_group.num_rows)]
        for f in self.filters:
            leaf = by_name[f.column]
            chunk = row_group.columns[leaf.column]
            if chunk.column_index is None or chunk.offset_index is None:
                continue
            _fetch(reader, chunk.column_index, f"the column index of {leaf.dotted_path()}")
            _fetch(reader, chunk.offset_index, f"the offset index of {leaf.dotted_path()}")
            file = bytes(reader[2].data)
            bounds = page_index.column_index(file, chunk)
            pages = page_index.offset_index(file, chunk).row_ranges(row_group.num_rows)
            might = [
                rows
                for i, rows in enumerate(pages)
                if not f.against_page(leaf, metadata, bounds, i, rows[1] - rows[0]).skip
            ]
            kept = _intersect(kept, might)
        return kept

    def read(self, leaf: Leaf, row_group: RowGroup, rows: list[tuple[int, int]], reader: tuple) -> pa.Array:
        """One column of ``row_group``, as an Arrow array of the rows in ``rows``.

        Reading the whole row group, the scan fetches the column chunk. Reading some of its rows,
        it fetches the chunk's offset index, which says where each page starts and which rows it
        holds, and then only the pages that hold those rows: every column's pages end at
        different rows, so each column reads its own.
        """
        chunk = row_group.columns[leaf.column]
        if rows == [(0, row_group.num_rows)] or chunk.offset_index is None:
            _fetch(reader, chunk.byte_range(), f"column {leaf.dotted_path()}")
            values = [t.value for t in read_column(bytes(reader[2].data), chunk, leaf).triples]
            return to_arrow([v for start, end in rows for v in values[start:end]], leaf)
        _fetch(reader, chunk.offset_index, f"the offset index of {leaf.dotted_path()}")
        index = page_index.offset_index(bytes(reader[2].data), chunk)
        pages = index.row_ranges(row_group.num_rows)
        wanted = [i for i, page in enumerate(pages) if _intersect([page], rows)]
        # A dictionary page, if the chunk has one, sits before the first data page: every page needs it.
        if index.pages[0].offset > chunk.byte_range().start:
            dictionary = Span(chunk.byte_range().start, index.pages[0].offset)
            _fetch(reader, dictionary, f"the dictionary page of {leaf.dotted_path()}")
        for i in wanted:
            _fetch(reader, index.pages[i].span(), f"page {i} of {leaf.dotted_path()}")
        decoded = read_column_pages(
            bytes(reader[2].data), chunk, leaf, [index.pages[i].offset for i in wanted]
        )
        # The pages decode one after another, so each value's row follows from its page's rows.
        at_row = [row for i in wanted for row in range(*pages[i])]
        value = dict(zip(at_row, (t.value for t in decoded.triples), strict=True))
        return to_arrow([value[row] for start, end in rows for row in range(start, end)], leaf)

    def schema(self) -> pa.Schema:
        # Read from the footer once: an operator above may ask with every batch it builds.
        if getattr(self, "_schema", None) is None:
            by_name = {leaf.dotted_path(): leaf for leaf in leaves(build(_footer(self.path).schema))}
            self._schema = pa.schema([arrow_field(by_name[name]) for name in self.columns])
        return self._schema


class TableScan(Operator):
    """Read a table of many Parquet files, one batch per row group of each file it opens (ch05).

    With ``metadata``, the scan first reads the table's metadata: a list of the table's files,
    each with the bounds of every column, as Iceberg keeps them in its manifests. A file whose
    bounds rule out every row is never opened. Without it, the scan lists the table's files and
    opens every one, and only a file's own footer can rule its rows out. Either way, each file it
    opens is read by a :class:`Scan` with the same filters, sharing one store, so the table's
    counters are every request the scan made.
    """

    #: The table's metadata, in the table's directory.
    METADATA = "metadata.json"

    def __init__(
        self, table: str | Path, columns: list[str], filters: list[Comparison] = (), metadata: bool = True
    ) -> None:
        detail = f"{Path(table).name}/: {', '.join(columns)}"
        if filters:
            detail += f"; {' AND '.join(map(str, filters))}"
        detail += "; by its metadata" if metadata else "; by its files"
        super().__init__("TableScan", detail, [])
        self.table = Path(table)
        self.columns = columns
        self.filters = list(filters)
        self.metadata = metadata
        self.skipped: dict[str, str] = {}
        """Each file the scan never opened, with the reason."""
        self.opened: list[str] = []
        """Each file the scan opened, in the order it opened them."""

    def batches(self) -> Iterator[pa.RecordBatch]:
        objects = MemoryStore()
        for path in sorted(self.table.rglob("*")):
            if path.is_file():
                objects.put(path.relative_to(self.table).as_posix(), path.read_bytes())
        store = TracingStore(objects, NetworkModel())
        if self.metadata:
            listing = json.loads(store.get(self.METADATA, All(), "the table's metadata").data)["files"]
        else:
            found = store.list("", "list the table's files")
            listing = [{"path": key} for key, _ in found if key.endswith(".parquet")]
        self.skipped, self.opened = {}, []
        self.count_requests(store)

        for entry in listing:
            why = self.ruled_out(entry) if self.metadata else None
            if why is not None:
                self.skipped[entry["path"]] = why
                continue
            self.opened.append(entry["path"])
            scan = Scan(self.table / entry["path"], self.columns, self.filters, store=(store, entry["path"]))
            for batch in scan.batches():
                self.count_requests(store)
                yield self.emit(batch)
            # The file's scan counted the rows it decoded and held; the table's are the sum.
            self.metrics.rows_in += scan.metrics.rows_in
            self.metrics.batches_in += scan.metrics.batches_in
            self.metrics.peak_memory_bytes = max(
                self.metrics.peak_memory_bytes, scan.metrics.peak_memory_bytes
            )
        self.count_requests(store)

    def ruled_out(self, entry: dict) -> str | None:
        """Why no row of a file can pass the filters, from its bounds in the table's metadata, or
        None if some row might."""
        for f in self.filters:
            bounds = entry["bounds"].get(f.column)
            if bounds is None:
                continue
            comparator = stats.Comparator[bounds["comparator"]]
            decision = f.against_bounds(
                comparator, bytes.fromhex(bounds["lower"]), bytes.fromhex(bounds["upper"])
            )
            if decision.skip:
                return f"{f}: {decision.why}"
        return None

    def count_requests(self, store: TracingStore) -> None:
        self.metrics.bytes_read = store.bytes_returned()
        self.metrics.requests = len(store.requests)

    def schema(self) -> pa.Schema:
        first = next(p for p in sorted(self.table.rglob("*.parquet")))
        return Scan(first, self.columns).schema()


class Filter(Operator):
    """Keep the rows of each batch for which ``predicate`` is true."""

    def __init__(self, child: Operator, description: str, predicate: BatchFunction) -> None:
        super().__init__("Filter", description, [child])
        self.child = child
        self.predicate = predicate

    def batches(self) -> Iterator[pa.RecordBatch]:
        for batch in self.child.batches():
            self.take(batch)
            yield self.emit(batch.filter(self.predicate(batch)))

    def schema(self) -> pa.Schema:
        return self.child.schema()


class Project(Operator):
    """Compute the output columns, each from an expression over the input batch."""

    def __init__(self, child: Operator, columns: dict[str, BatchFunction]) -> None:
        super().__init__("Project", ", ".join(columns), [child])
        self.child = child
        self.columns = columns

    def batches(self) -> Iterator[pa.RecordBatch]:
        for batch in self.child.batches():
            self.take(batch)
            arrays = [expression(batch) for expression in self.columns.values()]
            yield self.emit(pa.RecordBatch.from_arrays(arrays, names=list(self.columns)))

    def schema(self) -> pa.Schema:
        # An expression's type is the type of what it returns, so ask it of an empty batch.
        empty = pa.RecordBatch.from_pylist([], schema=self.child.schema())
        return pa.schema([(name, f(empty).type) for name, f in self.columns.items()])


def _fetch(reader: tuple, span: Span, why: str) -> None:
    """Fetch the parts of ``span`` the reader does not hold yet, one request each."""
    store, key, have = reader
    for part in have.missing(span):
        got = store.get(key, Bounded(part), why)
        have.add(got.span, got.data)


def _intersect(a: list[tuple[int, int]], b: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The rows in both lists of ``[start, end)`` ranges, as ranges in order."""
    out = []
    for start, end in a:
        for lo, hi in b:
            if max(start, lo) < min(end, hi):
                out.append((max(start, lo), min(end, hi)))
    out.sort()
    merged: list[tuple[int, int]] = []
    for start, end in out:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def arrow_type(leaf: Leaf) -> pa.DataType:
    """The Arrow type for a Parquet leaf column: its physical type, refined by its logical type."""
    logical = leaf.logical_type.name if leaf.logical_type is not None else None
    match leaf.physical_type.name, logical:
        case "BYTE_ARRAY", "STRING":
            return pa.string()
        case "INT32", "DATE":
            return pa.date32()
        case "INT32", None:
            return pa.int32()
        case "INT64", None:
            return pa.int64()
        case "DOUBLE", None:
            return pa.float64()
        case "BOOLEAN", None:
            return pa.bool_()
    raise NotImplementedError(f"no Arrow type for {leaf.physical_type.name} {logical}")


def arrow_field(leaf: Leaf) -> pa.Field:
    """The leaf as an Arrow field: a REQUIRED column can hold no nulls, and says so."""
    return pa.field(leaf.dotted_path(), arrow_type(leaf), nullable=leaf.repetitions[-1] != "required")


def to_arrow(values: list, leaf: Leaf) -> pa.Array:
    """A column's decoded values as an Arrow array, built buffer by buffer (ch02). Strings arrive
    as bytes, and dates as days since 1970, which is what a ``date32`` holds."""
    kind = arrow_type(leaf)
    if kind == pa.string():
        values = [None if v is None else v.decode() for v in values]
    return array_from(values, kind)


def _footer(path: Path):
    objects = MemoryStore()
    objects.put(path.name, path.read_bytes())
    return read_footer(TracingStore(objects, NetworkModel()), path.name, FooterOptions()).metadata
