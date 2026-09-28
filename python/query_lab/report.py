"""What a panel draws, as JSON: one function per experiment, run at build time and in the page.

A panel is a picture of this JSON and nothing else (CLAUDE.md). The page's JavaScript draws it and
never computes a count of its own. The same function runs in two places:

- **At build time**, ``python -m query_lab figures`` writes each panel's JSON into
  ``chapters/_generated/``, and the renderer embeds it in the page, so the panel draws at once,
  with nothing to download.
- **In the page**, when a reader asks, the lab runs the same function under Pyodide and redraws
  from what it returns. ``tests/browser/panels.mjs`` requires the two to be identical.

Every experiment takes the repository's root and the lab block's settings, and returns a JSON
object whose ``experiment`` names it.
"""

from __future__ import annotations

import datetime as dt
import struct
from pathlib import Path

import duckdb
from parquet_lab.object_store import MemoryStore, NetworkModel, TracingStore
from parquet_lab.reader import FooterOptions, read_footer
from parquet_lab.schema import build, leaves

from .metrics import Metrics
from .reference import clean_sql, observe


class ReportError(ValueError):
    """An experiment asked for something that does not exist."""


#: The result rows a panel shows: enough to see what the query returned, few enough to read.
PREVIEW_ROWS = 5


def plan(root: Path, query: str, sql: str | None = None) -> dict:
    """DuckDB's plan for a query in ``queries/``, as a tree: each operator with the planner's
    estimate of its output and the profile's measured rows in and out.

    ``sql`` replaces the file's text: a query the reader edited in the page. The report then says
    so, and carries the reader's text as its source, so the panel can show what ran.
    """
    path = root / "queries" / query
    if not path.is_file():
        raise ReportError(f"no query queries/{query}")
    source = path.read_text() if sql is None else sql
    if not clean_sql(source):
        raise ReportError("the query is empty")
    seen = observe(clean_sql(source))
    # The profile's root is the query; its one child is the plan's top operator.
    return {
        "experiment": "plan",
        "query": query,
        "edited": sql is not None,
        "source": source,
        "engine": f"DuckDB {duckdb.__version__}",
        "result_rows": len(seen.rows),
        "preview": {
            "columns": seen.columns,
            "rows": [[_json_value(v) for v in row] for row in seen.rows[:PREVIEW_ROWS]],
        },
        "root": _operator(seen.metrics, seen.profile["children"][0]),
    }


def _json_value(v: object) -> object:
    """A result value as JSON: numbers, strings, booleans and nulls as they are, anything else
    (a date, a decimal) as DuckDB's Python value prints it."""
    return v if v is None or isinstance(v, bool | int | float | str) else str(v)


def _operator(m: Metrics, raw: dict) -> dict:
    extra = raw.get("extra_info") or {}
    return {
        "operator": m.operator,
        "detail": _details(extra),
        # Not every operator carries an estimate (DuckDB gives none for ORDER_BY); None says so,
        # where a zero would claim the planner expected no rows.
        "estimated_rows_out": int(extra["Estimated Cardinality"])
        if "Estimated Cardinality" in extra
        else None,
        "rows_in": m.rows_in,
        "rows_out": m.rows_out,
        "children": [_operator(c, r) for c, r in zip(m.children, raw.get("children", []), strict=True)],
    }


def _details(extra: dict) -> list[list[str]]:
    """The profile's description of an operator, less the estimate, which has its own field."""
    out = []
    for key, value in extra.items():
        if key == "Estimated Cardinality":
            continue
        out.append([key, *([value] if isinstance(value, str) else [str(v) for v in value])])
    return out


#: The same orders in two files: written in date order, and shuffled (fixtures/generate.py).
GATHER_FIXTURES = ("orders-sorted.parquet", "orders-shuffled.parquet")

#: How many of each gather's reads the panel draws, evenly spaced through it: enough to see the
#: pattern.
PATTERN_READS = 160


def gather(root: Path, column: str) -> dict:
    """One column of the orders, gathered into date order through the cache model, once from
    each file: where date order is the order the rows are stored in, and where it is not.

    For each gather: the cache's counters, and the line of the column that every so many of its
    reads fell in, which is the pattern the panel draws.
    """
    # The engine needs pyarrow, which the plan panel does not load in the page: imported here, so
    # a plan runs with DuckDB alone.
    from . import memory
    from .cache import Cache
    from .operators import Scan
    from .plans import in_date_order

    gathers = []
    for fixture in GATHER_FIXTURES:
        table = Scan(root / "fixtures" / fixture, ["order_id", "order_date", column]).run()
        values = table.column(column).combine_chunks()
        if values.type not in memory.FIXED:
            raise ReportError(f"{column} is not a fixed-width column")
        width = memory.FIXED[values.type][0]
        order = in_date_order(table)
        cache = Cache()
        memory.gather(values, order, cache)
        every = max(1, len(order) // PATTERN_READS)
        pattern = [i * width // cache.line_bytes for i in order[::every][:PATTERN_READS]]
        gathers.append({"fixture": fixture, **cache.counters(), "pattern_every": every, "pattern": pattern})
    return {
        "experiment": "gather",
        "column": column,
        "engine": "the book's engine and cache model",
        "type": str(values.type),
        "width": width,
        "rows": len(values),
        "column_lines": -(-len(values) * width // cache.line_bytes),
        "cache": {"lines": cache.lines, "line_bytes": cache.line_bytes},
        "gathers": gathers,
    }


def pruning(root: Path, query: str) -> dict:
    """The engine's scan for a query in ``queries/``, pushed down as its plan in
    ``query_lab.plans`` pushes it, run against each orders file: which row groups the statistics
    let it skip and why, each row group's range of the filtered column, and the scan's counters.
    """
    # The engine needs pyarrow, which the plan panel does not load in the page.
    from .operators import Scan
    from .plans import PLANS

    if query not in PLANS:
        raise ReportError(f"no hand-written plan for queries/{query}")
    # Only a plan that is a scan with filters can be run against another file, by naming it.
    scan = PLANS[query](root)
    if not isinstance(scan, Scan) or not scan.filters:
        raise ReportError(f"the plan for queries/{query} is not a scan with filters")
    files = []
    for fixture in GATHER_FIXTURES:
        scan = PLANS[query](root, fixture)
        scan.run()
        column = scan.filters[0].column
        footer = read_footer(_store(root / "fixtures" / fixture), fixture, FooterOptions())
        leaf = next(x for x in leaves(build(footer.metadata.schema)) if x.dotted_path() == column)
        groups = []
        for index, row_group in enumerate(footer.metadata.row_groups):
            low, high = _bounds(leaf, row_group)
            groups.append(
                {
                    "rows": row_group.num_rows,
                    "min": low[0],
                    "max": high[0],
                    "min_label": low[1],
                    "max_label": high[1],
                    "read": index not in scan.skipped,
                    "why": scan.skipped.get(index, "the statistics cannot rule it out"),
                }
            )
        m = scan.metrics
        files.append(
            {
                "fixture": fixture,
                "row_groups": groups,
                "row_groups_read": m.batches_in,
                "rows_decoded": m.rows_in,
                "rows_out": m.rows_out,
                "bytes_read": m.bytes_read,
                "requests": m.requests,
                "file_bytes": (root / "fixtures" / fixture).stat().st_size,
            }
        )
    low, high = _window(scan.filters, leaf)
    return {
        "experiment": "pruning",
        "query": query,
        "engine": "the book's engine",
        "column": column,
        "filters": [str(f) for f in scan.filters],
        "window": {"min": low[0], "max": high[0], "min_label": low[1], "max_label": high[1]},
        "files": files,
    }


def _store(path: Path) -> TracingStore:
    objects = MemoryStore()
    objects.put(path.name, path.read_bytes())
    return TracingStore(objects, NetworkModel())


def _position(leaf, value: object) -> tuple[float, str]:
    """A value of the column as a number to place it by, and as text to label it with."""
    if isinstance(value, dt.date):
        return (value - dt.date(1970, 1, 1)).days, value.isoformat()
    if leaf.logical_type is not None and leaf.logical_type.name == "DATE":
        return value, (dt.date(1970, 1, 1) + dt.timedelta(days=value)).isoformat()
    return value, f"{value:,}" if isinstance(value, int) else f"{value:g}"


def _bounds(leaf, row_group) -> tuple[tuple[float, str], tuple[float, str]]:
    """A row group's minimum and maximum of the column, from its statistics."""
    formats = {"INT32": "<i", "INT64": "<q", "DOUBLE": "<d", "FLOAT": "<f"}
    fmt = formats.get(leaf.physical_type.name)
    st = row_group.columns[leaf.column].statistics
    if fmt is None or st is None:
        raise ReportError(f"{leaf.dotted_path()} has no numeric statistics to draw")
    low = st.min_value if st.min_value is not None else st.min
    high = st.max_value if st.max_value is not None else st.max
    return _position(leaf, struct.unpack(fmt, low)[0]), _position(leaf, struct.unpack(fmt, high)[0])


def _window(filters, leaf) -> tuple[tuple[float | None, str], tuple[float | None, str]]:
    """The range of values the filters let through, as the panel draws it: each end None when
    no filter bounds it."""
    low, high = (None, ""), (None, "")
    for f in filters:
        if f.op in (">", ">="):
            low = _position(leaf, f.value)
        elif f.op in ("<", "<="):
            high = _position(leaf, f.value)
        elif f.op == "=":
            low = high = _position(leaf, f.value)
    return low, high


EXPERIMENTS = {"plan": plan, "gather": gather, "pruning": pruning}


def panel_name(config: dict[str, str]) -> str:
    """The file a lab block's build-time JSON lives in, under ``chapters/_generated/``: named
    for the experiment and its settings, so the renderer finds it from the block alone."""
    settings = [Path(v).stem for k, v in sorted(config.items()) if k != "experiment"]
    return "-".join(["panel", config["experiment"], *settings]).replace("_", "-") + ".json"


def run(root: Path, config: dict[str, str]) -> dict:
    """Run the experiment a lab block names, with the block's other settings as arguments."""
    settings = dict(config)
    name = settings.pop("experiment", "")
    if name not in EXPERIMENTS:
        raise ReportError(f"no experiment {name!r}; the experiments are {', '.join(EXPERIMENTS)}")
    return EXPERIMENTS[name](root, **settings)
