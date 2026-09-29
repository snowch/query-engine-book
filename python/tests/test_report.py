"""query_lab.report: the JSON every panel draws, at build time and in the page."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from query_lab import figures, report
from query_lab.reference import observe, read_query

ROOT = Path(__file__).resolve().parents[2]
CONFIG = {"experiment": "plan", "query": "returned_unit_price.sql"}


def walk(node):
    yield node
    for c in node["children"]:
        yield from walk(c)


def test_the_plan_report_is_the_profile_with_its_estimates():
    data = report.run(ROOT, CONFIG)
    seen = observe(read_query(ROOT / "queries" / CONFIG["query"]))
    assert data["result_rows"] == len(seen.rows)
    ops = list(walk(data["root"]))
    assert [(o["operator"], o["rows_in"], o["rows_out"]) for o in ops] == [
        (m.operator, m.rows_in, m.rows_out) for m in seen.metrics.walk()
    ]
    assert all(o["estimated_rows_out"] > 0 for o in ops), "each operator of this plan carries an estimate"
    assert not any(k == "Estimated Cardinality" for o in ops for k, *_ in o["detail"])


def test_the_report_holds_no_time():
    """Counters, not time (CLAUDE.md, invariant 1): nothing in a panel's JSON may vary by run."""
    text = json.dumps(report.run(ROOT, CONFIG))
    for word in ("timing", "latency", "cpu_time", "seconds"):
        assert word not in text


def test_every_panel_is_generated_and_named_from_its_settings():
    for config in figures.PANELS:
        path = ROOT / "chapters" / "_generated" / report.panel_name(config)
        assert json.loads(path.read_text()) == report.run(ROOT, config)
    assert report.panel_name(CONFIG) == "panel-plan-returned-unit-price.json"


def test_an_edited_query_runs_and_says_so():
    sql = "SELECT status, count(*) AS orders FROM 'fixtures/orders-sorted.parquet' GROUP BY status ORDER BY status"
    data = report.run(ROOT, {**CONFIG, "sql": sql})
    assert data["edited"] and data["source"] == sql
    assert data["preview"]["columns"] == ["status", "orders"]
    assert [row[0] for row in data["preview"]["rows"]] == sorted(row[0] for row in data["preview"]["rows"])
    # DuckDB gives no estimate for an ORDER_BY: the report says none rather than zero.
    order_by = next(o for o in walk(data["root"]) if o["operator"] == "ORDER_BY")
    assert order_by["estimated_rows_out"] is None


def test_unknown_experiments_and_queries_are_refused():
    with pytest.raises(report.ReportError, match="no experiment"):
        report.run(ROOT, {"experiment": "nonsense"})
    with pytest.raises(report.ReportError, match="no query"):
        report.run(ROOT, {"experiment": "plan", "query": "missing.sql"})
    with pytest.raises(report.ReportError, match="empty"):
        report.run(ROOT, {**CONFIG, "sql": "-- nothing but a comment\n;"})


def test_the_plan_report_needs_no_pyarrow():
    """The page loads DuckDB alone for a plan panel (web/lab/python-worker.js), so the report
    module must import without pyarrow, and a plan must run without it."""
    import subprocess
    import sys

    code = (
        "import sys; sys.modules['pyarrow'] = None\n"
        "from pathlib import Path\n"
        "from query_lab import report\n"
        "report.run(Path('.'), {'experiment': 'plan', 'query': 'returned_unit_price.sql'})\n"
    )
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)


def test_a_plans_variants_are_reported_as_the_query_itself_is():
    data = report.run(ROOT, {**CONFIG, "variants": "pricier_returns.sql, shipped_unit_price.sql"})
    assert [v["query"] for v in data["variants"]] == ["pricier_returns.sql", "shipped_unit_price.sql"]
    for v in data["variants"]:
        assert v == report.run(ROOT, {"experiment": "plan", "query": v["query"]})
        assert v["label"], "a variant says what it changes, in its first comment"
    # The point of the variants: the planner's estimates stay where they were, and the rows move.
    estimates = {tuple(o["estimated_rows_out"] for o in walk(d["root"])) for d in [data, *data["variants"]]}
    measured = {tuple(o["rows_out"] for o in walk(d["root"])) for d in [data, *data["variants"]]}
    assert len(estimates) == 1 and len(measured) == 1 + len(data["variants"])
    assert (
        report.run(ROOT, {**CONFIG, "sql": "SELECT 1", "variants": "pricier_returns.sql"})["variants"] == []
    )
