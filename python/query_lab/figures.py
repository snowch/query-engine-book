"""Every generated fragment the chapters include: ``python -m query_lab figures``.

A chapter never types a number (CLAUDE.md, invariant 2). It includes a fragment from
``chapters/_generated/``, written here by running the engine or DuckDB on the fixtures. Every
fragment ends with a conditions line saying what computed it, on which fixture, with which
settings, so a reader can reproduce it.

``--check`` regenerates every fragment in memory and fails if a committed one differs: a change to
the engine, a fixture or DuckDB that moves a number fails the build until the fragments are
regenerated and committed.
"""

from __future__ import annotations

import json
import sys
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from . import plans, report
from .cache import LINE_BYTES, LINES
from .cpu import LANES, Predictor, VectorUnit, select_with_branch, select_without_branch
from .expressions import Counts, batches_of, evaluate, evaluate_row
from .memory import buffer_names, buffer_sizes
from .metrics import Metrics
from .operators import Comparison, Scan, TableScan
from .reference import Observation, bytes_read, connect, explain, files_opened, observe, read_query

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "chapters" / "_generated"


@dataclass(frozen=True)
class Figure:
    name: str
    make: Callable[[], str]
    #: The query in ``queries/`` the figure was computed from, if it was: a page marks the
    #: figure as the book's when the reader runs their own edit of that query. A figure made by
    #: one of the ``*_of(query, ...)`` functions knows its query already.
    query: str | None = None

    def __post_init__(self) -> None:
        if self.query is None:
            object.__setattr__(self, "query", getattr(self.make, "query", None))


def conditions(what: str, fixture: str) -> str:
    return f"\n*Computed by {what} on `fixtures/{fixture}`, at build time.*\n"


def duckdb_conditions(fixture: str) -> str:
    return conditions(f"DuckDB {duckdb.__version__} with one thread", fixture)


def plan_of(query: str, fixture: str, plan: str = "physical_plan") -> Callable[[], str]:
    """DuckDB's plan for a query, before it runs, as a table: one row per operator, top down.
    ``plan`` names which of DuckDB's plans (:func:`query_lab.reference.explain`); the logical
    plan as bound has no estimates, and its table no column for them.

    DuckDB draws its plan in box-drawing characters, and a monospace font without them (Android's,
    for one) pulls the boxes apart. A table reads the same on every screen, and the panel beside
    it draws the plan as a tree.
    """

    def make() -> str:
        rows = []
        estimated = plan != "logical_plan"

        def walk(node: dict) -> None:
            extra = {k: v for k, v in (node.get("extra_info") or {}).items() if v}
            estimate = extra.pop("Estimated Cardinality", None)
            # The scan's function repeats its operator's name; the rest says what the operator does.
            extra.pop("Function", None)
            does = "; ".join(f"{k}: {_cell(v)}" for k, v in extra.items())
            # The estimate sits beside the name, and the long details last, where a phone wraps them.
            guess = f"{int(estimate):,}" if estimate else "none"
            rows.append(f"| {node['name'].strip()} | " + (f"{guess} | " if estimated else "") + f"{does} |")
            for child in node.get("children", []):
                walk(child)

        walk(explain(read_query(ROOT / "queries" / query), plan=plan))
        if estimated:
            head = "| Operator | Rows out, estimated | What it does |\n|---|---:|---|\n"
        else:
            head = "| Operator | What it does |\n|---|---|\n"
        return head + "\n".join(rows) + "\n" + duckdb_conditions(fixture)

    make.query = query
    return make


def explain_of(query: str, fixture: str) -> Callable[[], str]:
    """DuckDB's plan for a query, as ``EXPLAIN`` draws it in a terminal, boxes and all (ch01).

    The page shows it in the book's own monospace font, which has every box-drawing character, so
    the boxes stay joined on any screen.
    """

    def make() -> str:
        con = connect()
        drawn = con.execute(f"EXPLAIN {read_query(ROOT / 'queries' / query)}").fetchall()[0][1]
        return "```diagram\n" + drawn.rstrip() + "\n```\n" + duckdb_conditions(fixture)

    make.query = query
    return make


#: What each kind of DuckDB operator says it did, for the journey of rows (``journey_of``).
JOURNEY_DETAIL = {"PARQUET_SCAN": "Filters", "FILTER": "Expression", "PROJECTION": "Projections"}


def journey_of(query: str, fixture: str) -> Callable[[], str]:
    """The rows of a one-path plan as they travel up it, from the file to the result: DuckDB's
    operators, bottom up, each with what it tests or computes and the rows it handed up (ch01)."""

    def make() -> str:
        text = read_query(ROOT / "queries" / query)
        steps = []
        node = explain(text)
        while True:
            steps.append(node)
            if not node.get("children"):
                break
            node = node["children"][0]
        measured = list(observe(text).metrics.walk())
        width = 44
        lines = [f"{'the file':<{width - 12}}{measured[-1].rows_in:>8,} rows"]
        for step, m in zip(reversed(steps), reversed(measured), strict=True):
            name = step["name"].strip()
            detail = (step.get("extra_info") or {}).get(JOURNEY_DETAIL.get(name, ""), "")
            detail = ", ".join(detail) if isinstance(detail, list) else str(detail)
            wrapped = textwrap.wrap(detail, 40) or [""]
            lines.append(f"  │  {name}")
            lines += [f"  │    {part}" for part in wrapped]
            lines.append("  ▼")
            lines.append(f"{'':<{width - 12}}{m.rows_out:>8,} rows")
        return "```diagram\n" + "\n".join(lines) + "\n```\n" + duckdb_conditions(fixture)

    make.query = query
    return make


def _cell(value: object) -> str:
    """A plan detail as table text: a list joined, and a pipe kept from ending the cell."""
    text = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
    return "`" + text.replace("|", "\\|") + "`"


def profile_table(seen: Observation) -> str:
    """The profile's counters beside the plan's estimates, one row per operator, top down."""
    rows = []
    for m, raw in zip(seen.metrics.walk(), _operators(seen.profile), strict=True):
        estimate = int(raw.get("extra_info", {}).get("Estimated Cardinality", 0))
        rows.append(f"| {m.operator} | {m.rows_in:,} | {estimate:,} | {m.rows_out:,} |")
    head = "| Operator | Rows in | Rows out, estimated | Rows out, measured |\n|---|---:|---:|---:|\n"
    return head + "\n".join(rows) + "\n"


#: The counters the engine's table shows, and their headings. Spill and shuffle stay zero until
#: the chapters that cause them, so they are left out until then.
ENGINE_COUNTERS = (
    ("rows_in", "Rows in"),
    ("rows_out", "Rows out"),
    ("batches_out", "Batches out"),
    ("bytes_read", "Bytes read"),
    ("requests", "Requests"),
    ("peak_memory_bytes", "Peak memory, bytes"),
)


def engine_table(metrics: Metrics) -> str:
    """The engine's counters, one row per operator, top down."""
    head = "| Operator | " + " | ".join(h for _, h in ENGINE_COUNTERS) + " |\n"
    head += "|---|" + "---:|" * len(ENGINE_COUNTERS) + "\n"
    rows = [
        f"| {m.operator} `{m.detail}` | "
        + " | ".join(f"{getattr(m, c):,}" for c, _ in ENGINE_COUNTERS)
        + " |"
        for m in metrics.walk()
    ]
    return head + "\n".join(rows) + "\n"


def engine_of(query: str, fixture: str) -> Callable[[], str]:
    def make() -> str:
        plan = plans.plan_for(ROOT, query)
        plan.run()
        return engine_table(plan.metrics) + conditions("the book's engine", fixture)

    make.query = query
    return make


def compare_of(query: str, fixture: str) -> Callable[[], str]:
    """The engine's operators beside DuckDB's partner for each, top down (plans.DUCKDB_PARTNERS)."""

    def make() -> str:
        plan = plans.plan_for(ROOT, query)
        plan.run()
        theirs = list(observe(read_query(ROOT / "queries" / query)).metrics.walk())
        rows = []
        for m, partner in zip(plan.metrics.walk(), plans.DUCKDB_PARTNERS[query], strict=True):
            duck = plans.duckdb_partner(theirs, partner) if partner else None
            rows.append(
                f"| {m.operator} `{m.detail}` | {m.rows_in:,} | {m.rows_out:,} | "
                + (f"{duck.operator} | {duck.rows_in:,} | {duck.rows_out:,} |" if duck else "none | | |")
            )
        head = (
            "| Your engine's operator | Rows in | Rows out | DuckDB's operator | Rows in | Rows out |\n"
            "|---|---:|---:|---|---:|---:|\n"
        )
        return (
            head
            + "\n".join(rows)
            + "\n"
            + conditions(f"the book's engine and DuckDB {duckdb.__version__} with one thread", fixture)
        )

    make.query = query
    return make


def profile_of(query: str, fixture: str) -> Callable[[], str]:
    """DuckDB's profile for a query, as the ``observe`` command prints it."""

    def make() -> str:
        return profile_table(observe(read_query(ROOT / "queries" / query))) + duckdb_conditions(fixture)

    make.query = query
    return make


def _operators(profile: dict):
    node = profile["children"][0]
    while True:
        yield node
        if not node["children"]:
            return
        node = node["children"][0]


#: The result rows a figure shows: enough to see the pattern, few enough to read.
FIRST_ROWS = 6


def first_rows_of(query: str, fixture: str, columns: list[str]) -> Callable[[], str]:
    """The first rows of a query's result, in the columns given."""

    def make() -> str:
        result = connect().execute(read_query(ROOT / "queries" / query)).arrow()
        rows = result.select(columns).slice(0, FIRST_ROWS).to_pylist()
        lines = ["| " + " | ".join(f"`{c}`" for c in columns) + " |", "|" + "---:|" * len(columns)]
        lines += ["| " + " | ".join(_value(r[c]) for c in columns) + " |" for r in rows]
        return "\n".join(lines) + "\n" + duckdb_conditions(fixture)

    make.query = query
    return make


def _array(column) -> pa.Array:
    """A column's one array as its engine built it. ``combine_chunks`` would copy it, and a copy
    drops a bitmap that marks every row valid, which is one of the things a figure shows."""
    return column.chunk(0) if column.num_chunks == 1 else column.combine_chunks()


def _value(v: object) -> str:
    return f"{v:,}" if isinstance(v, int) else str(v)


def _bytes(size: int | None) -> str:
    return "none" if size is None else f"{size:,}"


def arrow_buffers_of(query: str, fixture: str) -> Callable[[], str]:
    """Each column of a query's result as DuckDB hands it over in Arrow: its type, its nulls, and
    the bytes in each of its buffers."""

    def make() -> str:
        result = connect().execute(read_query(ROOT / "queries" / query)).arrow()
        lines = [
            "| Column | Arrow type | Nulls | Validity bitmap | Offsets | Values or data |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for name, column in zip(result.column_names, result.columns, strict=True):
            array = _array(column)
            sizes = buffer_sizes(array)
            payload = sizes.get("values", sizes.get("data"))
            lines.append(
                f"| `{name}` | `{array.type}` | {array.null_count:,} | {_bytes(sizes['validity'])} | "
                f"{_bytes(sizes.get('offsets'))} | {_bytes(payload)} |"
            )
        return "\n".join(lines) + "\n" + duckdb_conditions(fixture)

    make.query = query
    return make


def buffers_compare_of(query: str, fixture: str) -> Callable[[], str]:
    """The engine's result for a query beside DuckDB's, buffer by buffer."""

    def make() -> str:
        ours, _ = plans.orders_by_date(ROOT, fixture)
        theirs = connect().execute(read_query(ROOT / "queries" / query)).arrow()
        lines = ["| Column | Buffer | Your engine, bytes | DuckDB, bytes |", "|---|---|---:|---:|"]
        for name in ours.column_names:
            mine = buffer_sizes(_array(ours.column(name)))
            duck = buffer_sizes(_array(theirs.column(name)))
            for buffer in buffer_names(ours.column(name).type):
                lines.append(f"| `{name}` | {buffer} | {_bytes(mine[buffer])} | {_bytes(duck[buffer])} |")
        return (
            "\n".join(lines)
            + "\n"
            + conditions(f"the book's engine and DuckDB {duckdb.__version__} with one thread", fixture)
        )

    make.query = query
    return make


def gathers_table() -> str:
    """Each column of queries/orders_by_date.sql gathered into date order through the cache model,
    from the file stored in date order and from the shuffled one: the bytes each gather fetched."""
    runs = {f: plans.orders_by_date(ROOT, f) for f in report.GATHER_FIXTURES}
    lines = [
        "| Column | Bytes in its buffers | Bytes fetched, sorted file | Bytes fetched, shuffled file |",
        "|---|---:|---:|---:|",
    ]
    for name in plans.ORDERS_BY_DATE:
        table, _ = runs[report.GATHER_FIXTURES[0]]
        size = sum(s or 0 for s in buffer_sizes(_array(table.column(name))).values())
        fetched = [runs[f][1][name].bytes_fetched for f in report.GATHER_FIXTURES]
        lines.append(f"| `{name}` | {size:,} | {fetched[0]:,} | {fetched[1]:,} |")
    what = f"the book's engine and its cache model ({LINES} lines of {LINE_BYTES} bytes)"
    return (
        "\n".join(lines) + "\n" + f"\n*Computed by {what} on `fixtures/orders-sorted.parquet` and "
        "`fixtures/orders-shuffled.parquet`, at build time.*\n"
    )


def _scan_of(plan) -> Metrics:
    """The metrics of a plan's scan: the operator at the bottom of the tree."""
    return list(plan.metrics.walk())[-1]


def pushdown_table() -> str:
    """queries/early_march.sql three ways, against each orders file: with nothing pushed into the
    scan, with the columns pushed, and with the columns and the dates pushed. Then DuckDB, whose
    bytes are counted at the file system, and whose scan pushes both."""
    query = read_query(ROOT / "queries" / "early_march.sql")
    used = ["order_id", "order_date", "customer_id", "amount"]
    ways = [
        ("Nothing pushed", lambda f: plans.early_march_above(ROOT, f, plans.ORDERS_COLUMNS)),
        ("The columns pushed", lambda f: plans.early_march_above(ROOT, f, used)),
        ("The columns and the dates pushed", lambda f: plans.early_march(ROOT, f)),
    ]
    lines = [
        "| Scan | File | Row groups read | Rows decoded | Rows handed up | Bytes read | Requests |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for label, make in ways:
        for fixture in report.GATHER_FIXTURES:
            plan = make(fixture)
            plan.run()
            m = _scan_of(plan)
            lines.append(
                f"| {label} | `{fixture}` | {m.batches_in:,} | {m.rows_in:,} | {m.rows_out:,} | "
                f"{m.bytes_read:,} | {m.requests:,} |"
            )
    for fixture in report.GATHER_FIXTURES:
        sql = query.replace("orders-sorted.parquet", fixture)
        scan = list(observe(sql).metrics.walk())[-1]
        lines.append(
            f"| DuckDB's | `{fixture}` | not reported | not reported | {scan.rows_out:,} | "
            f"{bytes_read(sql):,} | not reported |"
        )
    what = f"the book's engine, and DuckDB {duckdb.__version__} with one thread, its reads counted at the file system"
    return (
        "\n".join(lines) + "\n" + f"\n*Computed by {what}, on `fixtures/orders-sorted.parquet` and "
        "`fixtures/orders-shuffled.parquet`, at build time.*\n"
    )


def row_groups_of(query: str, fixture: str) -> Callable[[], str]:
    """Each row group of ``fixture``, with its statistics for the column the query's plan filters
    on, and whether the engine's scan read it."""

    def make() -> str:
        data = report.pruning(ROOT, query)
        found = next(f for f in data["files"] if f["fixture"] == fixture)
        column = data["column"]
        lines = [
            f"| Row group | Rows | Smallest `{column}` | Largest `{column}` | Read by the scan |",
            "|---:|---:|---:|---:|---|",
        ]
        for i, g in enumerate(found["units"]):
            lines.append(
                f"| {i} | {g['rows']:,} | {g['min_label']} | {g['max_label']} | {'yes' if g['read'] else 'no'} |"
            )
        lines.append("")
        lines.append(
            f"The scan read {found['units_read']:,} of {len(found['units']):,} {found['unit']}s: "
            f"it decoded {found['rows_decoded']:,} rows, handed up {found['rows_out']:,}, and read "
            f"{found['bytes_read']:,} of the file's {found['file_bytes']:,} bytes."
        )
        return "\n".join(lines) + "\n" + conditions("the book's engine", fixture)

    make.query = query
    return make


def _pages_of(path: Path, column: str) -> int | None:
    """How many pages the page index lists for ``column`` across the file, or None without one."""
    from parquet_lab import page_index
    from parquet_lab.reader import FooterOptions, read_footer
    from parquet_lab.schema import build, leaves

    data = path.read_bytes()
    md = read_footer(report._store(path), path.name, FooterOptions()).metadata
    leaf = next(x for x in leaves(build(md.schema)) if x.dotted_path() == column)
    counts = [page_index.offset_index(data, g.columns[leaf.column]) for g in md.row_groups]
    return None if any(c is None for c in counts) else sum(len(c.pages) for c in counts)


#: The two files ch04 reads: the same sorted orders, cut into row groups, and into pages.
GRAIN_FIXTURES = ("orders-sorted.parquet", "orders-paged.parquet")


def grain_table() -> str:
    """What DuckDB reads of each file for queries/early_march_paged.sql, and for all its rows."""
    query = read_query(ROOT / "queries" / "early_march_paged.sql")
    lines = [
        "| File | Row groups | Pages of `order_date` | DuckDB's bytes read, the fortnight | "
        "DuckDB's bytes read, every row |",
        "|---|---:|---:|---:|---:|",
    ]
    for fixture in GRAIN_FIXTURES:
        sql = query.replace("orders-paged.parquet", fixture)
        every = sql.split("WHERE")[0]
        path = ROOT / "fixtures" / fixture
        pages = _pages_of(path, "order_date")
        groups = pq.ParquetFile(path).metadata.num_row_groups
        lines.append(
            f"| `{fixture}` | {groups:,} | {'no page index' if pages is None else f'{pages:,}'} | "
            f"{bytes_read(sql):,} | {bytes_read(every):,} |"
        )
    what = f"DuckDB {duckdb.__version__} with one thread, its reads counted at the file system"
    return (
        "\n".join(lines) + "\n" + f"\n*Computed by {what}, on `fixtures/orders-sorted.parquet` and "
        "`fixtures/orders-paged.parquet`, at build time.*\n"
    )


def paged_compare() -> str:
    """queries/early_march_paged.sql: your scan by row group, your scan by page, and DuckDB's."""
    sql = read_query(ROOT / "queries" / "early_march_paged.sql")
    lines = [
        "| Scan | Rows decoded | Rows handed up | Bytes read | Requests |",
        "|---|---:|---:|---:|---:|",
    ]
    by_group = plans.early_march(ROOT, "orders-paged.parquet")
    by_page = plans.early_march_by_page(ROOT)
    for label, scan in (("Yours, by row group", by_group), ("Yours, by page", by_page)):
        scan.run()
        m = scan.metrics
        lines.append(f"| {label} | {m.rows_in:,} | {m.rows_out:,} | {m.bytes_read:,} | {m.requests:,} |")
    duck = list(observe(sql).metrics.walk())[-1]
    lines.append(f"| DuckDB's | not reported | {duck.rows_out:,} | {bytes_read(sql):,} | not reported |")
    what = f"the book's engine and DuckDB {duckdb.__version__} with one thread, its reads counted at the file system"
    return "\n".join(lines) + "\n" + conditions(what, "orders-paged.parquet")


def dictionary_table() -> str:
    """orders-paged beside a copy the writer encodes as it does by default, with a dictionary for
    every column: each column's dictionary page, and what the page-by-page scan read of each."""
    import tempfile

    path = ROOT / "fixtures" / "orders-paged.parquet"
    columns = ["order_id", "order_date", "customer_id", "amount"]
    with tempfile.TemporaryDirectory() as tmp:
        # The fixture's own settings, but the writer's default dictionaries.
        copy = Path(tmp) / "orders-paged.parquet"
        pq.write_table(
            pq.read_table(path),
            copy,
            row_group_size=pq.ParquetFile(path).metadata.num_rows,
            compression="snappy",
            write_statistics=True,
            data_page_version="1.0",
            write_page_index=True,
            data_page_size=1024,
        )
        sizes, read = {}, {}
        for label, file in (("orders-paged", path), ("the default copy", copy)):
            md = pq.ParquetFile(file).metadata.row_group(0)
            chunks = {md.column(c).path_in_schema: md.column(c) for c in range(md.num_columns)}
            sizes[label] = {
                name: chunks[name].data_page_offset - chunks[name].dictionary_page_offset
                if chunks[name].dictionary_page_offset is not None
                else None
                for name in columns
            }
            scan = Scan(file, ["order_id", "customer_id", "amount"], plans.EARLY_MARCH, page_index=True)
            scan.run()
            read[label] = scan.metrics
    lines = [
        "| Column | Dictionary page, `orders-paged` | Dictionary page, the default copy |",
        "|---|---:|---:|",
    ]
    for name in columns:
        a, b = sizes["orders-paged"][name], sizes["the default copy"][name]
        lines.append(f"| `{name}` | {_bytes(a)} | {_bytes(b)} |")
    lines += [
        "",
        "| Scan by page | Rows decoded | Bytes read | Requests |",
        "|---|---:|---:|---:|",
    ]
    for label, m in read.items():
        lines.append(f"| {label} | {m.rows_in:,} | {m.bytes_read:,} | {m.requests:,} |")
    return (
        "\n".join(lines)
        + "\n"
        + "\n*Computed by the book's engine on `fixtures/orders-paged.parquet` and on a copy of it "
        f"that pyarrow {pa.__version__} writes, at build time, with its default dictionaries.*\n"
    )


def table_compare() -> str:
    """The fortnight from the table of monthly files: your table scan by its metadata and by its
    files, and DuckDB by a glob of the files and by the month in their directories' names."""
    lines = [
        "| Scan | Files opened | Requests | Bytes read | Rows decoded | Rows handed up |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, metadata in (("Yours, by the table's metadata", True), ("Yours, by the table's files", False)):
        scan = plans.early_march_table(ROOT, metadata=metadata)
        scan.run()
        m = scan.metrics
        lines.append(
            f"| {label} | {len(scan.opened):,} | {m.requests:,} | {m.bytes_read:,} | {m.rows_in:,} | {m.rows_out:,} |"
        )
    for label, query in (
        ("DuckDB's, by a glob of the files", "early_march_table.sql"),
        ("DuckDB's, by the month in the directory's name", "early_march_partition.sql"),
    ):
        sql = read_query(ROOT / "queries" / query)
        scan = list(observe(sql).metrics.walk())[-1]
        lines.append(
            f"| {label} | {files_opened(sql):,} | not reported | {bytes_read(sql):,} | not reported | "
            f"{scan.rows_out:,} |"
        )
    what = f"the book's engine and DuckDB {duckdb.__version__} with one thread, its reads counted at the file system"
    return "\n".join(lines) + "\n" + conditions(what, "orders-by-month/")


def storage_table() -> str:
    """The fortnight from each orders file, its rows tested by your engine and by the storage."""
    lines = [
        "| File | Where the rows are tested | Bytes over the network | Requests | Bytes the storage read |",
        "|---|---|---:|---:|---:|",
    ]
    for fixture in report.GATHER_FIXTURES:
        ours = plans.early_march(ROOT, fixture)
        ours.run()
        lines.append(
            f"| `{fixture}` | In your engine | {ours.metrics.bytes_read:,} | {ours.metrics.requests:,} | "
            f"{ours.metrics.bytes_read:,} |"
        )
        theirs = plans.early_march_in_storage(ROOT, fixture)
        theirs.run()
        lines.append(
            f"| `{fixture}` | In the storage | {theirs.metrics.bytes_read:,} | {theirs.metrics.requests:,} | "
            f"{theirs.storage.bytes_read:,} |"
        )
    return (
        "\n".join(lines) + "\n" + "\n*Computed by the book's engine and its storage that tests rows, on "
        "`fixtures/orders-sorted.parquet` and `fixtures/orders-shuffled.parquet`, at build time.*\n"
    )


def one_customer_table() -> str:
    """One customer's orders from the table of monthly files, by the table's metadata."""
    scan = TableScan(
        ROOT / "fixtures" / "orders-by-month",
        ["order_id", "order_date", "amount"],
        [Comparison("customer_id", "=", 17)],
    )
    rows = scan.run().num_rows
    m = scan.metrics
    metadata = json.loads((ROOT / "fixtures" / "orders-by-month" / "metadata.json").read_text())
    lines = [
        "| File | Rows | Smallest `customer_id` | Largest `customer_id` | Opened |",
        "|---|---:|---:|---:|---|",
    ]
    for entry in metadata["files"]:
        b = entry["bounds"]["customer_id"]
        low = int.from_bytes(bytes.fromhex(b["lower"]), "little", signed=True)
        high = int.from_bytes(bytes.fromhex(b["upper"]), "little", signed=True)
        opened = "yes" if entry["path"] in scan.opened else "no"
        lines.append(f"| `{entry['path']}` | {entry['rows']:,} | {low:,} | {high:,} | {opened} |")
    lines += [
        "",
        f"The scan opened {len(scan.opened):,} of {len(metadata['files']):,} files in {m.requests:,} requests, "
        f"read {m.bytes_read:,} bytes, decoded {m.rows_in:,} rows and handed up {rows:,}.",
    ]
    return "\n".join(lines) + "\n" + conditions("the book's engine", "orders-by-month/")


#: The batch sizes the evaluation table tries: one row, then batches up to DuckDB's vector size
#: and beyond it.
BATCH_SIZES = (16, 256, 2048, 20_000)


def batch_sizes_table() -> str:
    """queries/with_tax.sql's two expressions evaluated a row at a time and in batches of several
    sizes: the nodes the evaluator visited and the instructions its operators would run."""
    table = Scan(ROOT / "fixtures" / "orders-sorted.parquet", ["order_id", "amount", "quantity"]).run()
    lines = [
        "| How it evaluates | Batches | Nodes visited | Instructions | Lanes used | Rows kept |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    def row(label: str, batches: int, counts: Counts, unit: VectorUnit, kept: int) -> None:
        used = 100 * unit.values / (unit.instructions * unit.lanes)
        lines.append(
            f"| {label} | {batches:,} | {counts.dispatches:,} | {unit.instructions:,} | {used:.0f}% | {kept:,} |"
        )

    counts, unit, kept = Counts(), VectorUnit(), 0
    for r in table.to_pylist():
        if evaluate_row(plans.WITH_TAX_WHERE, r, counts, unit):
            evaluate_row(plans.WITH_TAX, r, counts, unit)
            kept += 1
    row("A row at a time", table.num_rows, counts, unit, kept)
    for size in BATCH_SIZES:
        counts, unit, kept, batches = Counts(), VectorUnit(), 0, 0
        for batch in batches_of(table, size):
            passing = batch.filter(evaluate(plans.WITH_TAX_WHERE, batch, counts, unit))
            evaluate(plans.WITH_TAX, passing, counts, unit)
            kept += passing.num_rows
            batches += 1
        row(f"In batches of {size:,} rows", batches, counts, unit, kept)
    return (
        "\n".join(lines)
        + "\n"
        + conditions(f"the book's engine and a vector unit of {LANES} lanes", "orders-sorted.parquet")
    )


def sorted_branches_table() -> str:
    """The random test of the branch panel, run on the amounts in the order the file stores them
    and in the order of the amounts themselves."""
    amounts = Scan(ROOT / "fixtures" / "orders-sorted.parquet", ["amount"]).run().column("amount").to_pylist()
    median = sorted(amounts)[len(amounts) // 2]
    lines = [
        "| The amounts in the order of | Kernel | Rows kept | Branches | Mispredictions |",
        "|---|---|---:|---:|---:|",
    ]
    for order, values in (("the file: by date", amounts), ("the amounts", sorted(amounts))):
        for kernel, select in (
            ("with a branch", select_with_branch),
            ("without a branch", select_without_branch),
        ):
            predictor = Predictor()
            kept = select(values, lambda v: v > median, predictor)
            lines.append(
                f"| {order} | {kernel} | {len(kept):,} | {predictor.branches:,} | {predictor.mispredictions:,} |"
            )
    return (
        "\n".join(lines)
        + "\n"
        + f"\nThe test is `amount > {median:g}`.\n"
        + conditions("the book's engine and branch model", "orders-sorted.parquet")
    )


def _grouped(keys: list[str], table) -> tuple[dict, int]:
    """The sorted orders' keys looked up in ``table`` through the cache model: its counters and
    the cache's misses."""
    from .cache import Cache

    table.cache = Cache()
    data = Scan(ROOT / "fixtures" / "orders-sorted.parquet", keys).run()
    columns = [data.column(k).to_pylist() for k in keys]
    for row in zip(*columns, strict=True):
        table.find(row[0] if len(row) == 1 else row)
    return table.counters(), table.cache.misses


def hash_and_perfect_table() -> str:
    """queries/orders_per_customer.sql's grouping through a hash table and a perfect one."""
    from .aggregate import HashTable, PerfectTable

    low, high = plans.customer_id_range(ROOT / "fixtures" / "orders-sorted.parquet")
    lines = [
        "| Table | Groups | Lookups | Slots probed | Resizes | Table bytes | Cache misses |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, table in (("A hash table", HashTable()), ("A perfect hash table", PerfectTable(low, high))):
        c, misses = _grouped(["customer_id"], table)
        lines.append(
            f"| {label} | {c['groups']:,} | {c['lookups']:,} | {c['probes']:,} | {c['resizes']:,} | "
            f"{c['table_bytes']:,} | {misses:,} |"
        )
    return (
        "\n".join(lines)
        + "\n"
        + conditions(
            f"the book's engine and cache model ({LINES} lines of {LINE_BYTES} bytes)",
            "orders-sorted.parquet",
        )
    )


#: The keys of the slow query in ch07's problem 7.3: the chapter's key, then with a second column.
WIDER_KEYS = (["customer_id"], ["customer_id", "status"], ["customer_id", "order_date"])


def wider_keys_table() -> str:
    """The orders grouped by the customer, then by the customer and a second column."""
    from .aggregate import HashTable

    lines = [
        "| GROUP BY | Groups | Slots probed | Table bytes | Cache misses |",
        "|---|---:|---:|---:|---:|",
    ]
    for keys in WIDER_KEYS:
        c, misses = _grouped(keys, HashTable())
        lines.append(
            f"| `{', '.join(keys)}` | {c['groups']:,} | {c['probes']:,} | {c['table_bytes']:,} | {misses:,} |"
        )
    return (
        "\n".join(lines)
        + "\n"
        + conditions(
            f"the book's engine and cache model ({LINES} lines of {LINE_BYTES} bytes)",
            "orders-sorted.parquet",
        )
    )


def build_sides_table() -> str:
    """The two ways of writing ch08's join: the side DuckDB built its table on, found in its
    profile, and the side your engine built on, with what it held and what probing cost."""
    from .aggregate import HashTable
    from .cache import Cache

    rows_of = {
        json.loads((ROOT / "fixtures" / f"{name}.json").read_text())["rows"]: name
        for name in ("customers", "orders-sorted")
    }
    lines = [
        "| Query | DuckDB builds on | Your engine builds on | Build rows held | Held bytes | Cache misses |",
        "|---|---|---|---:|---:|---:|",
    ]
    for query in ("orders_with_country.sql", "customers_with_orders.sql"):
        seen = observe(read_query(ROOT / "queries" / query))
        join = plans.duckdb_partner(list(seen.metrics.walk()), "HASH_JOIN")
        duck_build = rows_of[join.children[1].rows_out]
        plan = plans.plan_for(ROOT, query)
        plan.table = HashTable(cache=Cache())
        plan.run()
        ours = plan.build.path.stem
        lines.append(
            f"| `{query}` | `{duck_build}` | `{ours}` | {plan.build_rows:,} | {plan.held_bytes:,} | "
            f"{plan.table.cache.misses:,} |"
        )
    return (
        "\n".join(lines)
        + "\n"
        + conditions(
            f"the book's engine and cache model, and DuckDB {duckdb.__version__} with one thread",
            ORDERS_AND_CUSTOMERS,
        )
    )


def self_join_table() -> str:
    """ch08's problem 8.3: the orders joined to themselves on the customer, counted by DuckDB."""
    con = connect()
    orders = f"'{ROOT / 'fixtures' / 'orders-sorted.parquet'}'"
    total = con.execute(
        f"SELECT count(*) FROM {orders} AS a JOIN {orders} AS b ON a.customer_id = b.customer_id"
    ).fetchone()[0]
    top = con.execute(
        f"SELECT customer_id, count(*) AS n FROM {orders} GROUP BY customer_id ORDER BY n DESC, customer_id LIMIT 5"
    ).fetchall()
    lines = [
        "| Customer | Orders | Rows the join makes for them | Share of the join's rows |",
        "|---:|---:|---:|---:|",
    ]
    for customer, n in top:
        lines.append(f"| {customer} | {n:,} | {n * n:,} | {100 * n * n / total:.1f}% |")
    lines += [
        "",
        f"The join makes {total:,} rows from {con.execute(f'SELECT count(*) FROM {orders}').fetchone()[0]:,} orders.",
    ]
    return "\n".join(lines) + "\n" + duckdb_conditions("orders-sorted.parquet")


def sort_or_top_table() -> str:
    """ch09's problem 9.3: the ten largest orders, kept by the application after a full sort, or
    by the engine with a LIMIT."""
    lines = [
        "| Query | DuckDB's operator | Your engine's operator | Rows held | Comparisons | Rows handed up |",
        "|---|---|---|---:|---:|---:|",
    ]
    for query in ("orders_by_amount.sql", "top_orders.sql"):
        seen = json.dumps(explain(read_query(ROOT / "queries" / query)))
        duck = next(op for op in ("TOP_N", "ORDER_BY") if f'"{op}"' in seen)
        plan = plans.plan_for(ROOT, query)
        plan.run()
        lines.append(
            f"| `{query}` | `{duck}` | `{plan.metrics.operator}` | {plan.rows_held:,} | "
            f"{plan.comparisons.count:,} | {plan.metrics.rows_out:,} |"
        )
    return (
        "\n".join(lines)
        + "\n"
        + conditions(
            f"the book's engine and DuckDB {duckdb.__version__} with one thread", "orders-shuffled.parquet"
        )
    )


#: The memory limits ch10 runs DuckDB's sort within, around the smallest that lets it finish.
DUCKDB_LIMITS = ("1.5MB", "2MB", "2.5MB")


def memory_limits_table() -> str:
    """ch10's sort and top ten, run by DuckDB within small memory limits, with a temporary
    directory to spill to and without one."""
    import tempfile

    queries = [
        ("orders_by_amount.sql", True, "`orders_by_amount.sql`, with a temporary directory"),
        ("orders_by_amount.sql", False, "`orders_by_amount.sql`, with none"),
        ("top_orders.sql", False, "`top_orders.sql`, with none"),
    ]
    lines = ["| Query | " + " | ".join(DUCKDB_LIMITS) + " |", "|---|" + "---|" * len(DUCKDB_LIMITS)]
    for query, spill, label in queries:
        cells = []
        for limit in DUCKDB_LIMITS:
            con = connect()
            con.execute(f"SET memory_limit = '{limit}'")
            with tempfile.TemporaryDirectory() as temp:
                con.execute(f"SET temp_directory = '{temp if spill else ''}'")
                try:
                    con.execute(read_query(ROOT / "queries" / query)).fetchall()
                    cells.append("finishes")
                except duckdb.OutOfMemoryException:
                    cells.append("out of memory")
            con.close()
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n" + duckdb_conditions("orders-shuffled.parquet")


#: The fan-ins ch10's problem 10.3 sorts with, within a tenth of the rows' bytes.
FAN_INS = (2, 4, 8, 16)


def fan_in_table() -> str:
    """The shuffled orders sorted within a tenth of their bytes, merging more and more runs at once."""
    total = sum(b.get_total_buffer_size() for b in plans.orders_by_amount(ROOT).child.batches())
    lines = [
        "| Fan-in | Runs written | Merge passes | Rows spilled | Bytes spilled | Bytes read back |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for fan_in in FAN_INS:
        op = plans.orders_by_amount_within(ROOT, total // 10 + 1, fan_in)
        op.run()
        lines.append(
            f"| {fan_in} | {op.sorted_runs + op.merged_runs:,} | {op.passes:,} | {op.rows_spilled:,} | {op.temp.written:,} | {op.temp.read:,} |"
        )
    lines += ["", f"The rows take {total:,} bytes; the memory limit is {total // 10 + 1:,}."]
    return "\n".join(lines) + "\n" + conditions("the book's engine", "orders-shuffled.parquet")


def logical_of(query: str, fixture: str, rewritten: bool = False) -> Callable[[], str]:
    """The engine's plain logical plan for a query (ch11), or with ``rewritten`` the plan after
    ch12's rules, as a table: one row per step, top down."""

    def make() -> str:
        from .planner import logical_plan
        from .rules import RULES
        from .sql import parse

        logical = logical_plan(ROOT, parse(read_query(ROOT / "queries" / query)))
        for rule in RULES if rewritten else ():
            logical = rule(logical)
        steps = logical.walk()
        rows = [f"| {type(s).__name__} | `{str(s).partition(' ')[2]}` |" for s in steps]
        return (
            "| Step | What it does |\n|---|---|\n"
            + "\n".join(rows)
            + "\n"
            + conditions("the book's planner and its rules" if rewritten else "the book's planner", fixture)
        )

    make.query = query
    return make


def _scanned(metrics: Metrics, scan: str) -> tuple[int, str]:
    """The rows a plan's scans handed up, and its operators' names, top down."""
    walk = list(metrics.walk())
    return sum(m.rows_out for m in walk if m.operator == scan), ", ".join(m.operator for m in walk)


def plain_compare_of(query: str, fixture: str) -> Callable[[], str]:
    """The engine's plain plan for a query beside DuckDB's (ch11): the operators, the rows the
    scans handed up, the bytes read and the rows out."""

    def make() -> str:
        from .planner import plan

        text = read_query(ROOT / "queries" / query)
        ours = plan(ROOT, text)
        ours.run()
        seen = observe(text)
        rows = []
        for who, metrics, scan, read in (
            ("Your plain plan", ours.metrics, "Scan", sum(m.bytes_read for m in ours.metrics.walk())),
            ("DuckDB's plan", seen.metrics, "TABLE_SCAN", bytes_read(text)),
        ):
            scanned, operators = _scanned(metrics, scan)
            rows.append(f"| {who} | {operators} | {scanned:,} | {read:,} | {metrics.rows_out:,} |")
        head = "| Plan | Operators, top down | Rows from the scans | Bytes read | Rows out |\n|---|---|---:|---:|---:|\n"
        return (
            head
            + "\n".join(rows)
            + "\n"
            + conditions(
                f"the book's planner and engine, and DuckDB {duckdb.__version__} with one thread", fixture
            )
        )

    make.query = query
    return make


#: The fixtures a figure of the chapter's join query reads, as its conditions line names them.
ORDERS_AND_CUSTOMERS = "orders-sorted.parquet` and `fixtures/customers.parquet"

#: The queries problem 11.3 sets the plain plan against the hand-written ones for.
PLAIN_OR_WRITTEN = (
    "returned_unit_price.sql",
    "early_march.sql",
    "orders_per_customer.sql",
    "enterprise_orders.sql",
    "top_orders.sql",
)


def plain_or_written_table() -> str:
    """Five of the book's queries planned the plain way and by hand: the operators and the bytes
    read of each (ch11, problem 11.3)."""
    from .planner import plan

    rows = []
    for query in PLAIN_OR_WRITTEN:
        plain, written = plan(ROOT, read_query(ROOT / "queries" / query)), plans.plan_for(ROOT, query)
        cells = []
        for op in (plain, written):
            op.run()
            cells.append((_scanned(op.metrics, "Scan")[1], sum(m.bytes_read for m in op.metrics.walk())))
        rows.append(f"| `{query}` | {cells[0][0]} | {cells[0][1]:,} | {cells[1][0]} | {cells[1][1]:,} |")
    head = "| Query | Plain plan | Bytes read | Hand-written plan | Bytes read |\n|---|---|---:|---|---:|\n"
    return (
        head
        + "\n".join(rows)
        + "\n"
        + conditions(
            "the book's planner and engine",
            "orders-sorted.parquet`, `fixtures/orders-shuffled.parquet` and `fixtures/customers.parquet",
        )
    )


#: The rules DuckDB turns off in ch12's figure, alone and together, by DuckDB's names for them.
DUCKDB_RULES_OFF = ("", "filter_pushdown", "unused_columns")


def rules_off_table() -> str:
    """ch11's enterprise orders run by DuckDB with its rules on, and with each of two turned off
    (ch12): the operators, the rows from the scans and the bytes read."""
    text = read_query(ROOT / "queries" / "enterprise_orders.sql")
    rows = []
    for off in DUCKDB_RULES_OFF:
        setup = f"SET disabled_optimizers = '{off}'" if off else ""
        con = connect()
        if setup:
            con.execute(setup)
        seen = observe(text, con)
        scanned, operators = _scanned(seen.metrics, "TABLE_SCAN")
        label = f"`{off.replace(',', '`, `')}` off" if off else "every rule on"
        rows.append(f"| {label} | {operators} | {scanned:,} | {bytes_read(text, setup):,} |")
    head = "| DuckDB, with | Operators, top down | Rows from the scans | Bytes read |\n|---|---|---:|---:|\n"
    return head + "\n".join(rows) + "\n" + duckdb_conditions(ORDERS_AND_CUSTOMERS)


def rules_rebuild_table() -> str:
    """Every query with a plan written by hand, planned from its text by ch12's rules: the bytes
    each reads, beside the hand-written plan's."""
    from .planner import PlanError, plan
    from .rules import RULES

    rows = []
    for query in plans.PLANS:
        text = read_query(ROOT / "queries" / query)
        try:
            ours = plan(ROOT, text, RULES)
        except PlanError:
            continue
        written = plans.plan_for(ROOT, query)
        read = []
        for op in (ours, written):
            op.run()
            read.append(sum(m.bytes_read for m in op.metrics.walk()))
        rows.append(f"| `{query}` | {read[0]:,} | {read[1]:,} |")
    head = "| Query | Your rules' plan, bytes read | Hand-written plan, bytes read |\n|---|---:|---:|\n"
    return (
        head
        + "\n".join(rows)
        + "\n"
        + conditions(
            "the book's planner and rules",
            "orders-sorted.parquet`, `fixtures/orders-paged.parquet`, `fixtures/orders-shuffled.parquet` and "
            "`fixtures/customers.parquet",
        )
    )


def either_side_table() -> str:
    """Problem 12.3's query, whose condition reads both tables, planned by the rules and by DuckDB:
    where each put the condition, and what each read."""
    from .planner import plan
    from .rules import RULES

    text = read_query(ROOT / "queries" / "enterprise_or_large.sql")
    ours = plan(ROOT, text, RULES)
    ours.run()
    seen = observe(text)
    rows = []
    for who, metrics, scan, read in (
        ("Your rules' plan", ours.metrics, "Scan", sum(m.bytes_read for m in ours.metrics.walk())),
        ("DuckDB's plan", seen.metrics, "TABLE_SCAN", bytes_read(text)),
    ):
        scanned, operators = _scanned(metrics, scan)
        join = next(m for m in metrics.walk() if m.operator in ("HashJoin", "HASH_JOIN"))
        rows.append(
            f"| {who} | {operators} | {scanned:,} | {join.rows_out:,} | {read:,} | {metrics.rows_out:,} |"
        )
    head = (
        "| Plan | Operators, top down | Rows from the scans | Rows out of the join | Bytes read | Rows out |\n"
        "|---|---|---:|---:|---:|---:|\n"
    )
    return (
        head
        + "\n".join(rows)
        + "\n"
        + conditions(
            f"the book's planner and rules, and DuckDB {duckdb.__version__} with one thread",
            ORDERS_AND_CUSTOMERS,
        )
    )


#: The conditions problem 13.3 asks the planner and DuckDB to estimate, of the sorted orders.
MISESTIMATES = (
    "order_date < DATE '2024-04-01'",
    "status = 'returned'",
    "amount > 2000",
    "quantity = 1 AND amount > 300",
    "customer_id = 1",
)


def misestimates_table() -> str:
    """Conditions on the orders, the rows your planner and DuckDB estimate each keeps, and the rows
    it keeps (ch13, problem 13.3)."""
    from .cost import estimate
    from .planner import logical_plan
    from .rules import push_filters
    from .sql import parse

    con = connect()
    rows = []
    for condition in MISESTIMATES:
        text = f"SELECT order_id FROM 'fixtures/orders-sorted.parquet' WHERE {condition}"
        ours = estimate(ROOT, push_filters(logical_plan(ROOT, parse(text))))
        theirs = int(explain(text, con)["extra_info"]["Estimated Cardinality"])
        counted = con.execute(f"SELECT count(*) FROM ({text})").fetchone()[0]
        rows.append(f"| `{condition}` | {round(ours):,} | {theirs:,} | {counted:,} |")
    head = (
        "| Condition | Your planner's estimate | DuckDB's estimate | Rows it keeps |\n|---|---:|---:|---:|\n"
    )
    return (
        head
        + "\n".join(rows)
        + "\n"
        + conditions(
            f"the book's planner and DuckDB {duckdb.__version__} with one thread", "orders-sorted.parquet"
        )
    )


def join_estimates_table() -> str:
    """ch13's query planned by cost: each join's estimate and count, your planner's and DuckDB's."""
    from functools import partial

    from .cost import estimate, join_order
    from .planner import Join, logical_plan, physical_plan
    from .rules import prune_columns, push_filters
    from .sql import parse

    text = read_query(ROOT / "queries" / "asian_orders.sql")
    logical = logical_plan(ROOT, parse(text))
    for rule in (push_filters, partial(join_order, ROOT), prune_columns):
        logical = rule(logical)
    joins = [n for n in logical.walk() if isinstance(n, Join)]
    operator = physical_plan(ROOT, logical)
    operator.run()
    counted = [m for m in operator.metrics.walk() if m.operator == "HashJoin"]
    seen = observe(text)
    theirs = [m for m in seen.metrics.walk() if m.operator == "HASH_JOIN"]
    planned = _estimates(explain(text), "HASH_JOIN")
    rows = []
    for join, ours, duck, guess in zip(joins, counted, theirs, planned, strict=True):
        rows.append(
            f"| `{join.left_key} = {join.right_key}` | {round(estimate(ROOT, join)):,} | {ours.rows_out:,} | "
            f"{guess:,} | {duck.rows_out:,} |"
        )
    head = (
        "| Join, top down | Your estimate | Your rows | DuckDB's estimate | DuckDB's rows |\n"
        "|---|---:|---:|---:|---:|\n"
    )
    return (
        head
        + "\n".join(rows)
        + "\n"
        + conditions(
            f"the book's planner and DuckDB {duckdb.__version__} with one thread",
            "orders-sorted.parquet`, `fixtures/customers.parquet` and `fixtures/countries.parquet",
        )
    )


def _estimates(node: dict, name: str) -> list[int]:
    """The estimates DuckDB's plan gives the operators called ``name``, top down."""
    found = []
    if node["name"].strip() == name:
        found.append(int(node["extra_info"]["Estimated Cardinality"]))
    for child in node.get("children", []):
        found += _estimates(child, name)
    return found


def threads_table() -> str:
    """ch07's orders per customer run by DuckDB with one thread and with four (ch14): the rows each
    operator hands up, and the row groups of the file it reads."""
    text = read_query(ROOT / "queries" / "orders_per_customer.sql")
    walks = []
    for threads in (1, 4):
        con = connect()
        con.execute(f"SET threads = {threads}")
        walks.append(list(observe(text, con).metrics.walk()))
    rows = [
        f"| {one.operator} | {one.rows_out:,} | {four.rows_out:,} |" for one, four in zip(*walks, strict=True)
    ]
    head = "| Operator, top down | Rows out, one thread | Rows out, four threads |\n|---|---:|---:|\n"
    groups = "\n".join(
        f"| `{name}` | {pq.ParquetFile(ROOT / 'fixtures' / name).metadata.num_row_groups} |"
        for name in ("orders-sorted.parquet", "orders-paged.parquet")
    )
    return (
        head
        + "\n".join(rows)
        + "\n\n| File | Row groups |\n|---|---:|\n"
        + groups
        + "\n"
        + conditions(
            f"DuckDB {duckdb.__version__} with one thread and with four",
            "orders-sorted.parquet` and `fixtures/orders-paged.parquet",
        )
    )


def partitions_table() -> str:
    """Where DuckDB's hash of the customer id would send the orders and the customers, on four
    nodes (ch15)."""
    con = connect()
    counts = {}
    for name in ("orders-sorted.parquet", "customers.parquet"):
        counts[name] = dict(
            con.execute(
                f"SELECT hash(customer_id) % 4 AS node, count(*) FROM 'fixtures/{name}' GROUP BY node"
            ).fetchall()
        )
    rows = [
        f"| {node} | {counts['orders-sorted.parquet'].get(node, 0):,} | {counts['customers.parquet'].get(node, 0):,} |"
        for node in range(4)
    ]
    head = "| Node, `hash(customer_id) % 4` | Orders | Customers |\n|---:|---:|---:|\n"
    return (
        head
        + "\n".join(rows)
        + "\n"
        + duckdb_conditions("orders-sorted.parquet` and `fixtures/customers.parquet")
    )


def unique_keys_table() -> str:
    """The orders grouped by customer and by order on four simulated nodes, each after a shuffle
    and in two phases: the bytes each sends (ch15, problem 15.3)."""
    from . import distributed as d

    orders = d.place(ROOT / "fixtures" / "orders-sorted.parquet", ["order_id", "customer_id", "amount"], 4)
    rows = []
    for key in ("customer_id", "order_id"):
        after, two = d.aggregate_after_shuffle(orders, key), d.aggregate_in_two_phases(orders, key)
        rows.append(
            f"| `GROUP BY {key}` | {two.table().num_rows:,} | {after.shuffled:,} | {two.shuffled:,} |"
        )
    head = "| Query | Groups | Bytes shuffled, every order | Bytes shuffled, two phases |\n|---|---:|---:|---:|\n"
    return (
        head
        + "\n".join(rows)
        + "\n"
        + conditions("the book's engine on four simulated nodes", "orders-sorted.parquet")
    )


def heavy_customers_table() -> str:
    """The customers with the most orders, counted by DuckDB, and the five its sketch names (ch16)."""
    con = connect()
    top = con.execute(
        "SELECT customer_id, count(*) AS orders, count(*) / (SELECT count(*) FROM 'fixtures/orders-sorted.parquet') "
        "FROM 'fixtures/orders-sorted.parquet' GROUP BY customer_id ORDER BY orders DESC, customer_id LIMIT 5"
    ).fetchall()
    sketch = con.execute(
        "SELECT approx_top_k(customer_id, 5) FROM 'fixtures/orders-sorted.parquet'"
    ).fetchone()[0]
    rows = [f"| {c} | {n:,} | {share:.1%} |" for c, n, share in top]
    return (
        "| Customer | Orders | Share of all orders |\n|---:|---:|---:|\n"
        + "\n".join(rows)
        + f"\n\n`approx_top_k(customer_id, 5)` names customers {', '.join(map(str, sketch))}.\n"
        + duckdb_conditions("orders-sorted.parquet")
    )


def busy_month_table() -> str:
    """The orders partitioned by month over twelve nodes, and the rows a report on March reads on
    each (ch16, problem 16.3)."""
    con = connect()
    rows = con.execute(
        "SELECT month(order_date) AS node, count(*), count(*) FILTER (WHERE month(order_date) = 3) "
        "FROM 'fixtures/orders-sorted.parquet' GROUP BY node ORDER BY node"
    ).fetchall()
    lines = [f"| {node} | {held:,} | {march:,} |" for node, held, march in rows]
    head = "| Node, by month | Rows it holds | Rows the March report reads |\n|---:|---:|---:|\n"
    return head + "\n".join(lines) + "\n" + duckdb_conditions("orders-sorted.parquet")


def stages_table() -> str:
    """ch17's query run in stages on sixteen simulated nodes: each stage's tasks, rows and bytes."""
    from .stages import spend_by_country

    _, run = spend_by_country(ROOT, 16)
    rows = [f"| {i + 1}. {s.name} | {s.tasks} | {s.rows_in:,} | {s.bytes_out:,} |" for i, s in enumerate(run)]
    head = "| Stage | Tasks | Rows in | Bytes shuffled on |\n|---|---:|---:|---:|\n"
    return (
        head
        + "\n".join(rows)
        + "\n"
        + conditions(
            "the book's engine on sixteen simulated nodes",
            "orders-sorted.parquet` and `fixtures/customers.parquet",
        )
    )


def orders_recipe() -> str:
    """How the orders were generated, from the generator's own constants and manifest."""
    sys.path.insert(0, str(ROOT / "fixtures"))
    import generate  # noqa: PLC0415

    m = json.loads((ROOT / "fixtures" / "orders-sorted.json").read_text())
    total = sum(w for _, w in generate.STATUSES)
    lines = [
        "| Column | How it was generated |",
        "|---|---|",
        f"| `order_id` | 1 to {m['rows']:,}, in order |",
        f"| `status` | {', '.join(f'{s} {w / total:.0%}' for s, w in generate.STATUSES)} |",
        "| `quantity` | a whole number from {} to {}, each equally likely |".format(*generate.QUANTITY),
        "| `amount` | `quantity` times a unit price drawn evenly between {:g} and {:g} |".format(
            *generate.UNIT_PRICE
        ),
    ]
    return "\n".join(lines) + "\n" + conditions("`fixtures/generate.py`", "orders-sorted.parquet")


def fixtures_table() -> str:
    """Every fixture, from the manifests the generator wrote."""
    lines = ["| File | Rows | Row groups | Bytes | Why it exists |", "|---|---:|---:|---:|---|"]
    for path in sorted((ROOT / "fixtures").glob("*.json")):
        m = json.loads(path.read_text())
        lines.append(
            f"| `{m['name']}.parquet` | {m['rows']:,} | {len(m['row_groups'])} | {m['file_bytes']:,} | {m['why']} |"
        )
    return (
        "\n".join(lines) + "\n" + "\n*Read from the manifests `fixtures/generate.py` wrote, at build time.*\n"
    )


FIGURES = (
    Figure("returned-orders-explain", explain_of("returned_orders.sql", "orders-sorted.parquet")),
    Figure("returned-unit-price-explain", explain_of("returned_unit_price.sql", "orders-sorted.parquet")),
    Figure("returned-unit-price-journey", journey_of("returned_unit_price.sql", "orders-sorted.parquet")),
    Figure("lower-status-explain", explain_of("lower_status.sql", "orders-sorted.parquet")),
    Figure("orders-recipe", orders_recipe),
    Figure("returned-unit-price-engine", engine_of("returned_unit_price.sql", "orders-sorted.parquet")),
    Figure("returned-unit-price-compare", compare_of("returned_unit_price.sql", "orders-sorted.parquet")),
    Figure("lower-status-plan", plan_of("lower_status.sql", "orders-sorted.parquet")),
    Figure("lower-status-profile", profile_of("lower_status.sql", "orders-sorted.parquet")),
    Figure("fixtures", fixtures_table),
    Figure("orders-by-date-plan", plan_of("orders_by_date.sql", "orders-shuffled.parquet")),
    Figure(
        "orders-by-date-rows",
        first_rows_of(
            "orders_by_date.sql", "orders-shuffled.parquet", ["file_row_number", "order_id", "order_date"]
        ),
    ),
    Figure("orders-by-date-buffers", arrow_buffers_of("orders_by_date.sql", "orders-shuffled.parquet")),
    Figure("orders-by-date-compare", buffers_compare_of("orders_by_date.sql", "orders-shuffled.parquet")),
    Figure("orders-by-date-gathers", gathers_table),
    Figure("early-march-plan", plan_of("early_march.sql", "orders-sorted.parquet")),
    Figure("early-march-profile", profile_of("early_march.sql", "orders-sorted.parquet")),
    Figure("early-march-compare", compare_of("early_march.sql", "orders-sorted.parquet")),
    Figure("early-march-pushdown", pushdown_table, query="early_march.sql"),
    Figure("largest-orders-row-groups", row_groups_of("largest_orders.sql", "orders-sorted.parquet")),
    Figure("early-march-paged-plan", plan_of("early_march_paged.sql", "orders-paged.parquet")),
    Figure("grain", grain_table),
    Figure("early-march-paged-compare", paged_compare, query="early_march_paged.sql"),
    Figure("dictionary-pages", dictionary_table),
    Figure("early-march-table-plan", plan_of("early_march_table.sql", "orders-by-month/")),
    Figure("early-march-partition-plan", plan_of("early_march_partition.sql", "orders-by-month/")),
    Figure("early-march-table-compare", table_compare, query="early_march_table.sql"),
    Figure("storage", storage_table),
    Figure("one-customer-table", one_customer_table),
    Figure("with-tax-plan", plan_of("with_tax.sql", "orders-sorted.parquet")),
    Figure("with-tax-compare", compare_of("with_tax.sql", "orders-sorted.parquet")),
    Figure("batch-sizes", batch_sizes_table, query="with_tax.sql"),
    Figure("sorted-branches", sorted_branches_table),
    Figure("orders-per-customer-plan", plan_of("orders_per_customer.sql", "orders-sorted.parquet")),
    Figure("orders-per-status-plan", plan_of("orders_per_status.sql", "orders-sorted.parquet")),
    Figure("orders-per-customer-compare", compare_of("orders_per_customer.sql", "orders-sorted.parquet")),
    Figure("hash-and-perfect", hash_and_perfect_table),
    Figure("wider-keys", wider_keys_table),
    Figure("orders-with-country-plan", plan_of("orders_with_country.sql", "orders-sorted.parquet")),
    Figure("orders-with-country-compare", compare_of("orders_with_country.sql", "orders-sorted.parquet")),
    Figure("build-sides", build_sides_table, query="customers_with_orders.sql"),
    Figure("self-join", self_join_table),
    Figure("top-orders-plan", plan_of("top_orders.sql", "orders-shuffled.parquet")),
    Figure("orders-by-amount-plan", plan_of("orders_by_amount.sql", "orders-shuffled.parquet")),
    Figure("top-orders-compare", compare_of("top_orders.sql", "orders-shuffled.parquet")),
    Figure("sort-or-top", sort_or_top_table, query="orders_by_amount.sql"),
    Figure("memory-limits", memory_limits_table, query="orders_by_amount.sql"),
    Figure("fan-in", fan_in_table, query="orders_by_amount.sql"),
    Figure(
        "enterprise-orders-logical",
        plan_of("enterprise_orders.sql", ORDERS_AND_CUSTOMERS, "logical_plan"),
    ),
    Figure("enterprise-orders-plan", plan_of("enterprise_orders.sql", ORDERS_AND_CUSTOMERS)),
    Figure("enterprise-orders-plain", logical_of("enterprise_orders.sql", ORDERS_AND_CUSTOMERS)),
    Figure(
        "enterprise-orders-compare",
        plain_compare_of("enterprise_orders.sql", ORDERS_AND_CUSTOMERS),
    ),
    Figure("plain-or-written", plain_or_written_table),
    Figure("enterprise-orders-rules-off", rules_off_table, query="enterprise_orders.sql"),
    Figure("rules-rebuild", rules_rebuild_table),
    Figure("either-side", either_side_table, query="enterprise_or_large.sql"),
    Figure(
        "asian-orders-plan",
        plan_of(
            "asian_orders.sql",
            "orders-sorted.parquet`, `fixtures/customers.parquet` and `fixtures/countries.parquet",
        ),
    ),
    Figure("asian-orders-estimates", join_estimates_table, query="asian_orders.sql"),
    Figure("misestimates", misestimates_table),
    Figure("threads", threads_table, query="orders_per_customer.sql"),
    Figure("partitions", partitions_table),
    Figure("unique-keys", unique_keys_table),
    Figure("heavy-customers", heavy_customers_table),
    Figure("busy-month", busy_month_table),
    Figure("spend-by-country-plan", plan_of("spend_by_country.sql", ORDERS_AND_CUSTOMERS)),
    Figure("spend-by-country-stages", stages_table, query="spend_by_country.sql"),
    Figure(
        "enterprise-orders-rewritten",
        logical_of("enterprise_orders.sql", ORDERS_AND_CUSTOMERS, rewritten=True),
    ),
)


#: Every panel a chapter embeds, as its ``lab`` block's settings. Each one's JSON is computed here
#: at build time, embedded in the page by the renderer, and recomputed in the page on request.
PANELS = (
    {
        "experiment": "plan",
        "query": "returned_unit_price.sql",
        "variants": "pricier_returns.sql, shipped_unit_price.sql",
    },
    {"experiment": "gather", "column": "amount"},
    {"experiment": "pruning", "query": "early_march.sql"},
    {
        "experiment": "pruning",
        "query": "early_march_paged.sql",
        "fixtures": "orders-sorted.parquet, orders-paged.parquet",
    },
    {"experiment": "pruning", "query": "early_march_table.sql", "scans": "by its metadata, by its files"},
    {"experiment": "branches", "column": "amount"},
    {"experiment": "measure", "of": "aggregation"},
    {"experiment": "measure", "of": "joins"},
    {"experiment": "measure", "of": "sorting"},
    {"experiment": "measure", "of": "spilling"},
    {"experiment": "measure", "of": "planning"},
    {"experiment": "measure", "of": "rules"},
    {"experiment": "measure", "of": "join_orders"},
    {"experiment": "measure", "of": "parallelism"},
    {"experiment": "measure", "of": "shuffle"},
    {"experiment": "measure", "of": "skew"},
    {"experiment": "measure", "of": "stages"},
)


#: Each generated fragment computed from a query, by its file name: the query it was computed from.
QUERY_OF_FRAGMENT = {f"{f.name}.md": f.query for f in FIGURES if f.query}


def panel_json(config: dict[str, str]) -> str:
    return json.dumps(report.run(ROOT, config), indent=1) + "\n"


def outputs() -> dict[str, Callable[[], str]]:
    """Every generated file, by name: the fragments, then the panels' JSON."""
    out: dict[str, Callable[[], str]] = {f"{f.name}.md": f.make for f in FIGURES}
    for config in PANELS:
        out[report.panel_name(config)] = lambda config=config: panel_json(config)
    return out


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale = []
    OUT.mkdir(parents=True, exist_ok=True)
    made = outputs()
    for name, make in made.items():
        path = OUT / name
        text = make()
        if check:
            if not path.exists() or path.read_text() != text:
                stale.append(path.name)
        else:
            path.write_text(text)
    orphans = sorted(p.name for p in OUT.glob("*") if p.is_file() and p.name not in made)
    if check:
        if stale or orphans:
            print("stale generated fragments (run `make figures` and commit):", ", ".join(stale + orphans))
            return 1
        print(f"  {len(made)} generated fragments and panels are current")
        return 0
    for name in orphans:
        (OUT / name).unlink()
    print(f"wrote {len(made)} fragments and panels to {OUT.relative_to(ROOT)}")
    return 0
