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
    assert all(o["estimated_rows_out"] > 0 for o in ops), "every DuckDB operator carries an estimate"
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


def test_unknown_experiments_and_queries_are_refused():
    with pytest.raises(report.ReportError, match="no experiment"):
        report.run(ROOT, {"experiment": "nonsense"})
    with pytest.raises(report.ReportError, match="no query"):
        report.run(ROOT, {"experiment": "plan", "query": "missing.sql"})
