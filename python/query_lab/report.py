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

from pathlib import Path

import duckdb

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


EXPERIMENTS = {"plan": plan}


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
