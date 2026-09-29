"""Sorting within a memory limit: runs spilled, then merged (ch10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from query_lab import plans, report
from query_lab.reference import connect, read_query

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def duckdbs():
    return connect().execute(read_query(ROOT / "queries" / "orders_by_amount.sql")).fetchall()


@pytest.fixture(scope="module")
def total():
    return sum(b.get_total_buffer_size() for b in plans.orders_by_amount(ROOT).child.batches())


@pytest.mark.parametrize("share, fan_in", [(2.0, 8), (0.5, 8), (0.1, 2), (0.1, 3), (0.1, 16), (0.05, 4)])
def test_the_external_sort_returns_duckdbs_order_whatever_its_memory(share, fan_in, duckdbs, total):
    op = plans.orders_by_amount_within(ROOT, int(total * share) + 1, fan_in)
    assert [tuple(r.values()) for r in op.run().to_pylist()] == duckdbs
    assert op.metrics.peak_memory_bytes <= max(op.memory_limit, total // 10), (
        "one batch may exceed a tiny limit"
    )
    op.metrics.check()


def test_rows_that_fit_are_never_spilled(total):
    op = plans.orders_by_amount_within(ROOT, total + 1)
    op.run()
    assert op.temp.written == op.rows_spilled == op.sorted_runs == op.passes == 0


def test_every_byte_written_is_read_back_and_each_pass_spills_every_row_but_the_last(total):
    for fan_in in (2, 4, 16):
        op = plans.orders_by_amount_within(ROOT, total // 10 + 1, fan_in)
        op.run()
        assert op.temp.read == op.temp.written and not op.temp.files
        assert op.rows_spilled == op.metrics.rows_in * op.passes


def test_a_larger_fan_in_never_spills_more(total):
    spilled = []
    for fan_in in (2, 3, 4, 8, 16):
        op = plans.orders_by_amount_within(ROOT, total // 10 + 1, fan_in)
        op.run()
        spilled.append(op.rows_spilled)
    assert spilled == sorted(spilled, reverse=True)


def test_the_spilling_report_is_the_engines(total):
    data = report.run(ROOT, {"experiment": "measure", "of": "spilling"})
    fits, half, tenth = data["cases"]
    assert fits["measured"] == 0 < half["measured"] < tenth["measured"]
    assert all(c["reference"]["value"] == total for c in data["cases"])
