"""The counters in COUNTERS.md: the structure, its invariants, and DuckDB's profile read into it."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from query_lab.metrics import COUNTERS, Metrics, MetricsError
from query_lab.reference import observe

ROOT = Path(__file__).resolve().parents[2]
SORTED = ROOT / "fixtures" / "orders-sorted.parquet"


def plan() -> Metrics:
    scan = Metrics(
        "Scan", "orders", rows_in=100, rows_out=100, batches_in=2, batches_out=2, bytes_read=640, requests=3
    )
    keep = Metrics(
        "Filter", "amount > 10", rows_in=100, rows_out=40, batches_in=2, batches_out=2, children=[scan]
    )
    return Metrics(
        "Project", "order_id", rows_in=40, rows_out=40, batches_in=2, batches_out=2, children=[keep]
    )


def test_the_specification_and_the_code_name_the_same_counters():
    spec = (ROOT / "COUNTERS.md").read_text()
    table = spec.split("## The structure", 1)[1].split("## Invariants", 1)[0]
    documented = re.findall(r"^\| `(\w+)` \|", table, re.M)
    assert documented == ["operator", "detail", *COUNTERS]


def test_a_consistent_plan_passes_and_totals_add_up():
    p = plan()
    p.check()
    assert p.total("bytes_read") == 640
    assert p.total("rows_in") == 240
    assert [m.operator for m in p.walk()] == ["Project", "Filter", "Scan"]


def test_json_round_trips():
    p = plan()
    assert Metrics.from_json(p.to_json()) == p
    assert list(p.to_json())[2:-1] == list(COUNTERS)


@pytest.mark.parametrize(
    "break_it, message",
    [
        (lambda p: setattr(p.children[0], "rows_in", 99), "rows_in is 99"),
        (lambda p: setattr(p.children[0], "batches_in", 1), "batches_in is 1"),
        (lambda p: setattr(p, "bytes_read", 1), "only a leaf reads storage"),
        (lambda p: setattr(p.children[0].children[0], "requests", -1), "negative"),
        (lambda p: setattr(p.children[0].children[0], "batches_out", 0), None),
    ],
)
def test_each_invariant_is_enforced(break_it, message):
    p = plan()
    break_it(p)
    with pytest.raises(MetricsError, match=message):
        p.check()


def test_duckdbs_profile_reads_into_the_same_tree():
    sql = f"SELECT order_id, amount FROM read_parquet('{SORTED}') WHERE amount > 1000"
    seen = observe(sql)
    m = seen.metrics
    assert m.rows_out == len(seen.rows)
    scan = list(m.walk())[-1]
    assert scan.operator == "TABLE_SCAN" and "Function: READ_PARQUET" in scan.detail
    # Invariant 2 holds for DuckDB's tree too, because it is how rows_in is derived.
    for op in m.walk():
        if op.children:
            assert op.rows_in == sum(c.rows_out for c in op.children)


def test_duckdbs_rows_scanned_does_not_show_pruning():
    """COUNTERS.md says the book never compares a leaf's rows_in with DuckDB's. This is why: a
    filter that the sorted file's statistics let DuckDB skip most row groups for still reports
    every row in the file as scanned. If a DuckDB upgrade changes that, this test says so."""
    sql = f"SELECT count(*) FROM read_parquet('{SORTED}') WHERE order_date < DATE '2024-01-10'"
    scan = list(observe(sql).metrics.walk())[-1]
    total = observe(f"SELECT count(*) FROM read_parquet('{SORTED}')").rows[0][0]
    assert scan.rows_out < total / 10
    assert scan.rows_in == total
