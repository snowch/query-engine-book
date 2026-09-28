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

from collections.abc import Callable, Iterator
from pathlib import Path

import pyarrow as pa
from parquet_lab.column import read_column
from parquet_lab.object_store import Bounded, MemoryStore, NetworkModel, TracingStore
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


class Scan(Operator):
    """Read columns of a Parquet file, one batch per row group, with the Parquet book's reader.

    The file sits in the reader's simulated object store, so every byte the scan reads is a
    request the store logged: the footer first, then each column chunk it needs. This scan reads
    every row group and hands up every row. ch03 teaches it to read less.
    """

    def __init__(self, path: str | Path, columns: list[str]) -> None:
        super().__init__("Scan", f"{Path(path).name}: {', '.join(columns)}", [])
        self.path = Path(path)
        self.columns = columns

    def batches(self) -> Iterator[pa.RecordBatch]:
        data = self.path.read_bytes()
        key = self.path.name
        objects = MemoryStore()
        objects.put(key, data)
        store = TracingStore(objects, NetworkModel())
        footer = read_footer(store, key, FooterOptions())
        # The reader decodes only bytes the store returned; anything else reads as zeros.
        have = Fetched(len(data))
        for request in store.requests:
            if request.returned is not None:
                have.add(request.returned, data[request.returned.start : request.returned.end])
        by_name = {leaf.dotted_path(): leaf for leaf in leaves(build(footer.metadata.schema))}
        wanted = [by_name[name] for name in self.columns]
        schema = pa.schema([arrow_field(leaf) for leaf in wanted])

        for row_group in footer.metadata.row_groups:
            arrays = []
            for leaf in wanted:
                chunk = row_group.columns[leaf.column]
                got = store.get(key, Bounded(chunk.byte_range()), f"column {leaf.dotted_path()}")
                have.add(got.span, got.data)
                decoded = read_column(bytes(have.data), chunk, leaf)
                arrays.append(to_arrow([t.value for t in decoded.triples], leaf))
            batch = pa.RecordBatch.from_arrays(arrays, schema=schema)
            self.take(batch)
            self.metrics.bytes_read = store.bytes_returned()
            self.metrics.requests = len(store.requests)
            yield self.emit(batch)

    def schema(self) -> pa.Schema:
        by_name = {leaf.dotted_path(): leaf for leaf in leaves(build(_footer(self.path).schema))}
        return pa.schema([arrow_field(by_name[name]) for name in self.columns])


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
