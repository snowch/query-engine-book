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
import json
import struct
from pathlib import Path

import duckdb
from parquet_lab import page_index
from parquet_lab.object_store import MemoryStore, NetworkModel, TracingStore
from parquet_lab.reader import FooterOptions, read_footer
from parquet_lab.schema import build, leaves

from .metrics import Metrics
from .reference import clean_sql, observe


class ReportError(ValueError):
    """An experiment asked for something that does not exist."""


#: The result rows a panel shows: enough to see what the query returned, few enough to read.
PREVIEW_ROWS = 5


def plan(root: Path, query: str, sql: str | None = None, variants: str = "") -> dict:
    """DuckDB's plan for a query in ``queries/``, as a tree: each operator with the planner's
    estimate of its output and the profile's measured rows in and out.

    ``sql`` replaces the file's text: a query the reader edited in the page. The report then says
    so, and carries the reader's text as its source, so the panel can show what ran.

    ``variants`` names other query files, separated by commas: changes to the query a reader can
    try with one press, each reported the same way, so the page draws them with nothing to run.
    An edited query carries none.
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
        "label": _label(source),
        "variants": [] if sql is not None else [plan(root, v) for v in _names(variants)],
    }


def _names(setting: str) -> list[str]:
    """A setting that lists files, separated by commas, as a list of names."""
    return [name.strip() for name in setting.split(",") if name.strip()]


def _label(source: str) -> str:
    """What a query file says it is: its first comment, after the chapter's label."""
    first = next((line for line in source.splitlines() if line.startswith("--")), "")
    text = first.removeprefix("--").split(":", 1)[-1].strip()
    return text[:1].upper() + text[1:]


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


def pruning(root: Path, query: str, fixtures: str = "", scans: str = "") -> dict:
    """The engine's scan for a query in ``queries/``, pushed down as its plan in
    ``query_lab.plans`` pushes it, run against each of ``fixtures`` (the two orders files unless
    the block names others): what the scan skipped and why, each unit's range of the filtered
    column, and the scan's counters.

    A unit is a row group, or, where the scan reads the page index and the file has one, a page of
    the filtered column (ch04), or, for a table of many files, a file (ch05). ``scans`` names
    scans in ``query_lab.plans.SCANS`` to set side by side instead, where the query's file cannot
    say which way each reads.
    """
    # The engine needs pyarrow, which the plan panel does not load in the page.
    from .operators import Scan, TableScan
    from .plans import PLANS, SCANS

    if scans:
        runs = [(name, SCANS[name](root)) for name in _names(scans)]
    else:
        if query not in PLANS:
            raise ReportError(f"no hand-written plan for queries/{query}")
        # Only a plan that is a scan with filters can be run against another file, by naming it.
        scan = PLANS[query](root)
        if not isinstance(scan, Scan) or not scan.filters:
            raise ReportError(f"the plan for queries/{query} is not a scan with filters")
        runs = [(fixture, PLANS[query](root, fixture)) for fixture in _names(fixtures) or GATHER_FIXTURES]
    files = []
    for label, scan in runs:
        scan.run()
        if isinstance(scan, TableScan):
            files.append({**_table_units(scan, label), **_counters(scan)})
            continue
        fixture = label
        column = scan.filters[0].column
        data = (root / "fixtures" / fixture).read_bytes()
        footer = read_footer(_store(root / "fixtures" / fixture), fixture, FooterOptions())
        leaf = next(x for x in leaves(build(footer.metadata.schema)) if x.dotted_path() == column)
        by_page = scan.page_index and all(
            g.columns[leaf.column].column_index for g in footer.metadata.row_groups
        )
        units = []
        for index, row_group in enumerate(footer.metadata.row_groups):
            if by_page:
                units += _pages(data, leaf, row_group, scan.kept.get(index, []), scan.skipped.get(index))
            else:
                low, high = _bounds(leaf, row_group)
                units.append(
                    _unit(row_group.num_rows, low, high, index not in scan.skipped, scan.skipped.get(index))
                )
        files.append(
            {
                "fixture": fixture,
                "unit": "page" if by_page else "row group",
                "units": units,
                "units_read": sum(u["read"] for u in units),
                **_counters(scan),
                "file_bytes": len(data),
            }
        )
    column = scan.filters[0].column
    if isinstance(scan, TableScan):
        low, high = _window_of_values(scan.filters, _is_date(scan, column))
    else:
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


def _counters(scan) -> dict:
    m = scan.metrics
    return {
        "rows_decoded": m.rows_in,
        "rows_out": m.rows_out,
        "bytes_read": m.bytes_read,
        "requests": m.requests,
    }


#: How to read a bound the table's metadata keeps, by the comparator that orders it.
BOUND_FORMATS = {"I32": "<i", "I64": "<q", "F64": "<d", "F32": "<f"}


def _is_date(scan, column: str) -> bool:
    metadata = json.loads((scan.table / scan.METADATA).read_text())
    return any(entry.startswith(f"{column}: date") for entry in metadata["schema"])


def _typed(value: float, is_date: bool) -> tuple[float, str]:
    if is_date:
        return value, (dt.date(1970, 1, 1) + dt.timedelta(days=value)).isoformat()
    return value, f"{value:,}" if isinstance(value, int) else f"{value:g}"


def _table_units(scan, label: str) -> dict:
    """A table's files as units: each file's bounds of the filtered column, from the table's
    metadata, and whether the scan opened it."""
    column = scan.filters[0].column
    is_date = _is_date(scan, column)
    metadata = json.loads((scan.table / scan.METADATA).read_text())
    units = []
    for entry in metadata["files"]:
        bounds = entry["bounds"][column]
        fmt = BOUND_FORMATS[bounds["comparator"]]
        low = _typed(struct.unpack(fmt, bytes.fromhex(bounds["lower"]))[0], is_date)
        high = _typed(struct.unpack(fmt, bytes.fromhex(bounds["upper"]))[0], is_date)
        read = entry["path"] in scan.opened
        units.append(_unit(entry["rows"], low, high, read, scan.skipped.get(entry["path"])))
    return {
        "fixture": f"{scan.table.name}/",
        "label": label,
        "unit": "file",
        "units": units,
        "units_read": len(scan.opened),
        "file_bytes": sum(e["bytes"] for e in metadata["files"]),
    }


def _window_of_values(filters, is_date: bool) -> tuple[tuple, tuple]:
    low, high = (None, ""), (None, "")
    for f in filters:
        value = (f.value - dt.date(1970, 1, 1)).days if isinstance(f.value, dt.date) else f.value
        if f.op in (">", ">="):
            low = _typed(value, is_date)
        elif f.op in ("<", "<="):
            high = _typed(value, is_date)
        elif f.op == "=":
            low = high = _typed(value, is_date)
    return low, high


def _unit(rows: int, low: tuple, high: tuple, read: bool, why: str | None) -> dict:
    return {
        "rows": rows,
        "min": low[0],
        "max": high[0],
        "min_label": low[1],
        "max_label": high[1],
        "read": read,
        "why": why or "nothing rules it out",
    }


def _pages(data: bytes, leaf, row_group, kept: list, skipped: str | None) -> list[dict]:
    """Each page of the column in ``row_group``, from its page index: its rows, its bounds, and
    whether the scan read it, which it did if the page holds any row the scan kept."""
    column_index = page_index.column_index(data, row_group.columns[leaf.column])
    ranges = page_index.offset_index(data, row_group.columns[leaf.column]).row_ranges(row_group.num_rows)
    out = []
    for i, (start, end) in enumerate(ranges):
        read = any(max(start, a) < min(end, b) for a, b in kept)
        low = _position(leaf, _decode(leaf, column_index.min_values[i]))
        high = _position(leaf, _decode(leaf, column_index.max_values[i]))
        out.append(
            _unit(end - start, low, high, read, skipped or (None if read else "the page index rules it out"))
        )
    return out


def _decode(leaf, plain: bytes) -> float:
    formats = {"INT32": "<i", "INT64": "<q", "DOUBLE": "<d", "FLOAT": "<f"}
    fmt = formats.get(leaf.physical_type.name)
    if fmt is None:
        raise ReportError(f"{leaf.dotted_path()} has no numeric bounds to draw")
    return struct.unpack(fmt, plain)[0]


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
    st = row_group.columns[leaf.column].statistics
    if st is None:
        raise ReportError(f"{leaf.dotted_path()} has no statistics to draw")
    low = st.min_value if st.min_value is not None else st.min
    high = st.max_value if st.max_value is not None else st.max
    return _position(leaf, _decode(leaf, low)), _position(leaf, _decode(leaf, high))


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


#: The thresholds of the branch panel's sweep, in tenths of the way up the sorted values.
SWEEP_TENTHS = range(11)


def branches(root: Path, column: str) -> dict:
    """Which rows of the sorted orders pass a test, found with a branch and without one, through
    the branch predictor model (ch06).

    Three cases: a test on the column the file is sorted by, which keeps a run of rows; a test on
    ``column`` that keeps about half the rows at random, with a branch; and the same test without
    a branch. Then a sweep of the second test across thresholds that keep from nearly every row to
    none, both ways, which is the curve the panel draws once the reader has predicted.
    """
    # The engine needs pyarrow, which the plan panel does not load in the page: imported here, so
    # a plan runs with DuckDB alone.
    from .cpu import Predictor, select_with_branch, select_without_branch
    from .operators import Scan

    fixture = "orders-sorted.parquet"
    table = Scan(root / "fixtures" / fixture, ["order_date", column]).run()
    values = table.column(column).to_pylist()
    if not all(isinstance(v, int | float) for v in values):
        raise ReportError(f"{column} is not a numeric column")
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    dates = table.column("order_date").to_pylist()
    halfway = dt.date(2024, 7, 1)

    def case(label: str, test: str, kernel: str, of: list, passes) -> dict:
        predictor = Predictor()
        select = select_with_branch if kernel == "with a branch" else select_without_branch
        kept = select(of, passes, predictor)
        return {
            "label": label,
            "test": test,
            "kernel": kernel,
            "rows": len(of),
            "kept": len(kept),
            **predictor.counters(),
        }

    above = f"{column} > {median:g}"
    cases = [
        case("a run", f"order_date < {halfway}", "with a branch", dates, lambda d: d < halfway),
        case("at random", above, "with a branch", values, lambda v: v > median),
        case("at random, no branch", above, "without a branch", values, lambda v: v > median),
    ]
    sweep = []
    for tenth in SWEEP_TENTHS:
        # The value this many tenths of the way up the sorted values: a test for values above it
        # keeps the rest.
        threshold = ordered[min(len(ordered) - 1, tenth * len(ordered) // 10)]
        point = {"threshold": threshold}
        for kernel, select in (("with", select_with_branch), ("without", select_without_branch)):
            predictor = Predictor()
            point["kept"] = len(select(values, lambda v, t=threshold: v > t, predictor))
            point[kernel] = predictor.mispredictions
        sweep.append(point)
    return {
        "experiment": "branches",
        "column": column,
        "fixture": fixture,
        "engine": "the book's engine and branch model",
        "rows": len(values),
        "cases": cases,
        "sweep": sweep,
    }


EXPERIMENTS = {"plan": plan, "gather": gather, "pruning": pruning, "branches": branches}


def panel_name(config: dict[str, str]) -> str:
    """The file a lab block's build-time JSON lives in, under ``chapters/_generated/``: named
    for the experiment and its settings, so the renderer finds it from the block alone."""
    settings = [Path(name).stem for k, v in sorted(config.items()) if k != "experiment" for name in _names(v)]
    return "-".join(["panel", config["experiment"], *settings]).replace("_", "-") + ".json"


def run(root: Path, config: dict[str, str]) -> dict:
    """Run the experiment a lab block names, with the block's other settings as arguments."""
    settings = dict(config)
    name = settings.pop("experiment", "")
    if name not in EXPERIMENTS:
        raise ReportError(f"no experiment {name!r}; the experiments are {', '.join(EXPERIMENTS)}")
    return EXPERIMENTS[name](root, **settings)
