"""Simulated workers: the rows they hand up, and the work each does (ch14)."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pytest

from query_lab.parallel import PER_CUSTOMER, RETURNED, Morsel, assign, run
from query_lab.reference import connect, read_query

ROOT = Path(__file__).resolve().parents[2]
SORTED = ROOT / "fixtures" / "orders-sorted.parquet"
PAGED = ROOT / "fixtures" / "orders-paged.parquet"


def test_each_morsel_goes_to_the_worker_free_soonest():
    assert assign([5, 5, 5, 5, 5], 2) == [0, 1, 0, 1, 0]
    assert assign([9, 1, 1, 1], 2) == [0, 1, 1, 1]


@pytest.mark.parametrize("workers", [1, 3, 4, 16])
def test_the_workers_share_every_morsel_and_nothing_else(workers):
    r = run(SORTED, *RETURNED[:2], workers)
    assert sum(r.workers) == r.total and len(r.workers) == workers


def test_the_morsels_together_hand_up_duckdbs_rows():
    columns, pipeline, _ = RETURNED
    ours = pa.concat_tables(pipeline(Morsel(SORTED, i, columns)).run() for i in range(10))
    theirs = connect().execute(read_query(ROOT / "queries" / "returned_unit_price.sql")).fetchall()
    assert sorted(ours.column("order_id").to_pylist()) == sorted(r[0] for r in theirs)


def test_one_worker_combines_nothing_and_more_workers_combine_more():
    afters = [run(SORTED, PER_CUSTOMER[0], PER_CUSTOMER[1], w, PER_CUSTOMER[2]).after for w in (1, 2, 4, 8)]
    assert afters[0] == 0
    assert afters[1:] == sorted(afters[1:]) and afters[1] > 0


def test_one_row_group_gains_nothing_from_more_workers():
    assert run(PAGED, *RETURNED[:2], 8).speedup == 1


def test_ten_near_equal_morsels_on_four_workers_finish_after_three():
    r = run(SORTED, *RETURNED[:2], 4)
    busiest = r.workers.index(max(r.workers))
    assert assign(r.morsels, 4).count(busiest) == 3
    assert 3 <= r.speedup <= 3.5
