"""A query run in stages on simulated nodes, and what a failed node costs (ch17)."""

from __future__ import annotations

from pathlib import Path

import pytest

from query_lab import stages
from query_lab.reference import connect, read_query

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("nodes", [1, 4, 16])
def test_the_stages_give_duckdbs_rows(nodes):
    result, _ = stages.spend_by_country(ROOT, nodes)
    theirs = connect().execute(read_query(ROOT / "queries" / "spend_by_country.sql")).fetchall()
    ours = [tuple(r.values()) for r in result.to_pylist()]
    assert [r[:2] for r in ours] == [r[:2] for r in theirs]
    assert all(abs(a[2] - b[2]) < 1e-6 for a, b in zip(ours, theirs, strict=True))


def test_each_stage_reads_the_one_before_and_the_last_runs_once():
    _, run = stages.spend_by_country(ROOT, 4)
    assert [s.feeds for s in run[1:]] == [[s.name] for s in run[:-1]]
    assert run[-1].tasks == 1 and run[-1].bytes_out == 0


def test_the_less_that_is_kept_the_more_a_failure_reruns():
    _, run = stages.spend_by_country(ROOT, 16)
    for failed in range(len(run)):
        counts = [stages.rerun(run, failed, kept) for kept in stages.KEPT]
        assert counts == sorted(counts, reverse=True)
    assert stages.rerun(run, len(run) - 1, "nowhere") == sum(s.tasks for s in run)
