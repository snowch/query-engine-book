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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from . import plans, report
from .cache import LINE_BYTES, LINES
from .memory import buffer_names, buffer_sizes
from .metrics import Metrics
from .operators import Scan
from .reference import Observation, bytes_read, connect, explain, observe, read_query

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "chapters" / "_generated"


@dataclass(frozen=True)
class Figure:
    name: str
    make: Callable[[], str]


def conditions(what: str, fixture: str) -> str:
    return f"\n*Computed by {what} on `fixtures/{fixture}`, at build time.*\n"


def duckdb_conditions(fixture: str) -> str:
    return conditions(f"DuckDB {duckdb.__version__} with one thread", fixture)


def plan_of(query: str, fixture: str) -> Callable[[], str]:
    """DuckDB's plan for a query, before it runs, as a table: one row per operator, top down.

    DuckDB draws its plan in box-drawing characters, and a monospace font without them (Android's,
    for one) pulls the boxes apart. A table reads the same on every screen, and the panel beside
    it draws the plan as a tree.
    """

    def make() -> str:
        rows = []

        def walk(node: dict) -> None:
            extra = dict(node.get("extra_info") or {})
            estimate = extra.pop("Estimated Cardinality", None)
            # The scan's function repeats its operator's name; the rest says what the operator does.
            extra.pop("Function", None)
            does = "; ".join(f"{k}: {_cell(v)}" for k, v in extra.items())
            # The estimate sits beside the name, and the long details last, where a phone wraps them.
            guess = f"{int(estimate):,}" if estimate else "none"
            rows.append(f"| {node['name'].strip()} | {guess} | {does} |")
            for child in node.get("children", []):
                walk(child)

        walk(explain(read_query(ROOT / "queries" / query)))
        head = "| Operator | Rows out, estimated | What it does |\n|---|---:|---|\n"
        return head + "\n".join(rows) + "\n" + duckdb_conditions(fixture)

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

    return make


def compare_of(query: str, fixture: str) -> Callable[[], str]:
    """The engine's operators beside DuckDB's partner for each, top down (plans.DUCKDB_PARTNERS)."""

    def make() -> str:
        plan = plans.plan_for(ROOT, query)
        plan.run()
        theirs = {m.operator: m for m in observe(read_query(ROOT / "queries" / query)).metrics.walk()}
        rows = []
        for m, partner in zip(plan.metrics.walk(), plans.DUCKDB_PARTNERS[query], strict=True):
            duck = theirs[partner] if partner else None
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

    return make


def profile_of(query: str, fixture: str) -> Callable[[], str]:
    """DuckDB's profile for a query, as the ``observe`` command prints it."""

    def make() -> str:
        return profile_table(observe(read_query(ROOT / "queries" / query))) + duckdb_conditions(fixture)

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
    Figure("returned-unit-price-plan", plan_of("returned_unit_price.sql", "orders-sorted.parquet")),
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
    Figure("early-march-pushdown", pushdown_table),
    Figure("largest-orders-row-groups", row_groups_of("largest_orders.sql", "orders-sorted.parquet")),
    Figure("early-march-paged-plan", plan_of("early_march_paged.sql", "orders-paged.parquet")),
    Figure("grain", grain_table),
    Figure("early-march-paged-compare", paged_compare),
    Figure("dictionary-pages", dictionary_table),
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
)


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
