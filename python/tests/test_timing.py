"""The timed blocks: each case runs, the clock copes with fast and slow work, the profiler accounts
for every operator, and what the chapters say about their timings holds at a desk.

The comparisons a chapter's prose makes (``Timing.faster``) are each several times apart in a
browser, where the page times them; at a desk the margins are smaller, but the order is the same.
A failure here means a sentence in a chapter may be wrong on a reader's machine.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from query_lab import timing
from query_lab.first_plan import returned_unit_price

ROOT = Path(__file__).resolve().parents[2]


def test_a_slow_case_is_timed_once_and_a_fast_one_in_groups():
    seconds, runs, _ = timing.clock(lambda: time.sleep(timing.SLOW))
    assert runs == 1 and seconds >= timing.SLOW
    seconds, runs, _ = timing.clock(lambda: None)
    assert runs > 1 + timing.GROUPS and seconds < timing.GROUP


def test_every_operator_of_the_engines_plan_is_profiled_and_the_scan_spends_the_most():
    plan = returned_unit_price(ROOT)
    profile = timing.engine_profile(plan)
    start = time.perf_counter()
    plan.run()
    whole = time.perf_counter() - start
    found = profile()
    assert [(op, depth) for op, depth, _ in found] == [
        ("Project", 0),
        ("Filter", 1),
        ("Filter", 2),
        ("Scan", 3),
    ]
    # Each operator's own time, its children's left out, adds up to the whole run.
    assert sum(s for *_, s in found) == pytest.approx(whole, rel=0.1)
    assert max(found, key=lambda p: p[2])[0] == "Scan"


def test_a_timings_cases_are_described_without_a_time():
    for name in timing.TIMINGS:
        described = timing.describe(ROOT, name)
        assert described["of"] == name and described["title"] and described["data"]
        assert all(set(c) == {"label", "detail"} for c in described["cases"])


@pytest.mark.parametrize("name", list(timing.TIMINGS))
def test_what_a_chapter_says_of_its_timing_holds(name):
    t = timing.timing(ROOT, name)
    t.setup()
    timing.warm_up()
    times = [timing.clock(c.work)[0] for c in t.cases]
    assert t.faster, f"{name}: a timing the prose compares nothing in"
    for a, b in t.faster:
        assert times[a] < times[b], f"{name}: {t.cases[a].label} took longer than {t.cases[b].label}"
