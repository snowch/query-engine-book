"""Pipelines that push batches from a scan into sinks (ch18)."""

from __future__ import annotations

from pathlib import Path

import pytest

from query_lab import push
from query_lab.reference import connect, read_query

ROOT = Path(__file__).resolve().parents[2]


def duckdb(query: str) -> list[tuple]:
    return connect().execute(read_query(ROOT / "queries" / query)).fetchall()


@pytest.mark.parametrize("listen", [True, False])
def test_exists_gives_duckdbs_answer_and_obeys_the_counters(listen):
    _, found = push.any_returned(ROOT, listen)
    found.metrics.check()
    assert [(found.found,)] == duckdb("any_returned.sql")


def test_a_source_that_listens_stops_after_the_first_row_group_with_a_match():
    listening, _ = push.any_returned(ROOT, listen=True)
    deaf, _ = push.any_returned(ROOT, listen=False)
    assert listening.metrics.batches_out == 1 < deaf.metrics.batches_out
    assert listening.metrics.bytes_read < deaf.metrics.bytes_read
    # Read to the end, the scan hands up every returned order, as a count would.
    assert [(deaf.metrics.rows_out,)] == duckdb("returned_count.sql")


def ours(table) -> list[tuple]:
    return [tuple(r.values()) for r in table.to_pylist()]


def same(a: list[tuple], b: list[tuple]) -> bool:
    return [r[0] for r in a] == [r[0] for r in b] and all(
        abs(x[1] - y[1]) < 1e-6 for x, y in zip(a, b, strict=True)
    )


@pytest.mark.parametrize("query", ["big_returners.sql", "big_returners_materialized.sql"])
def test_the_pushed_big_returners_are_duckdbs(query):
    _, groups = push.big_returners(ROOT)
    for g in groups:
        g.metrics.check()
    assert same(ours(push.result_of(groups)), duckdb(query))


def test_the_pulled_big_returners_are_duckdbs():
    _, (totals, average) = push.big_returners_pulled(ROOT)
    result = push.over_average(totals.to_batches()[0], average.column("average")[0].as_py())
    assert same(ours(result), duckdb("big_returners.sql"))


def test_a_tee_hands_every_row_to_every_consumer_from_one_scan():
    scans, groups = push.big_returners(ROOT)
    assert len(scans) == 1
    assert all(g.metrics.rows_in == scans[0].metrics.rows_out for g in groups)


def test_a_scan_each_reads_the_bytes_of_one_scan_once_for_each_consumer():
    pushed, _ = push.big_returners(ROOT)
    for k in (1, 2, 3):
        consumers = (push.TOTALS, push.AVERAGE, push.TOTALS)[:k]
        pulled, _ = push.big_returners_pulled(ROOT, consumers)
        assert sum(s.metrics.bytes_read for s in pulled) == k * pushed[0].metrics.bytes_read
