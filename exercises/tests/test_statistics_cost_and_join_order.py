"""Graders for ch13's problems. Each expected answer is derived at test time: by counting the
orders, or by trying every order of joins. None is stored."""

from __future__ import annotations

import itertools
import math
import random
from pathlib import Path

import pytest
from statistics_cost_and_join_order import best_order, fraction_above, histogram

from query_lab.operators import Scan

ROOT = Path(__file__).resolve().parents[2]
ORDERS = ROOT / "fixtures" / "orders-sorted.parquet"


def amounts() -> list[float]:
    return Scan(ORDERS, ["amount"]).run().column("amount").to_pylist()


# Problem 13.1 ----------------------------------------------------------------------------------


@pytest.mark.problem("13.1")
def test_problem_13_1_the_bounds_split_the_sample_evenly():
    sample = random.Random(13).sample(amounts(), 1000)
    bounds = histogram(sample, 10)
    assert len(bounds) == 11 and bounds == sorted(bounds)
    assert bounds[0] == min(sample) and bounds[-1] == max(sample)
    for low, high in itertools.pairwise(bounds):
        inside = sum(1 for v in sample if low < v <= high)
        assert 80 <= inside <= 120, f"the bucket from {low} to {high} holds {inside} of 1000"


@pytest.mark.problem("13.1")
@pytest.mark.parametrize("x", [50, 100, 250, 500, 1000, 1500, 2000, 2400])
def test_problem_13_1_a_sampled_histogram_estimates_amount_above_x(x):
    values = amounts()
    bounds = histogram(random.Random(131).sample(values, 1000), 20)
    counted = sum(1 for v in values if v > x) / len(values)
    assert abs(fraction_above(bounds, x) - counted) < 0.02, (
        f"amount > {x}: you estimate {fraction_above(bounds, x):.3f}, the orders hold {counted:.3f}"
    )


@pytest.mark.problem("13.1")
def test_problem_13_1_beyond_the_bounds():
    bounds = [0.0, 10.0, 20.0]
    assert fraction_above(bounds, -5) == 1
    assert fraction_above(bounds, 25) == 0
    assert fraction_above(bounds, 10) == pytest.approx(0.5)
    assert fraction_above(bounds, 5) == pytest.approx(0.75)


# Problem 13.2 ----------------------------------------------------------------------------------


def cost(order, rows, selectivity) -> float | None:
    """The rows every join in ``order`` hands up, added together; None if a table has no
    condition with any table before it."""
    total, joined = 0.0, [order[0]]
    for table in order[1:]:
        if not any(frozenset((table, t)) in selectivity for t in joined):
            return None
        joined.append(table)
        size = math.prod(rows[t] for t in joined)
        size *= math.prod(s for pair, s in selectivity.items() if pair <= set(joined))
        total += size
    return total


def instance(rng: random.Random, n: int):
    names = [f"t{i}" for i in range(n)]
    rows = {t: rng.choice([10, 100, 1000, 10_000, 100_000]) * rng.randint(1, 9) for t in names}
    selectivity = {}
    for i in range(1, n):
        j = rng.randrange(i)
        selectivity[frozenset((names[i], names[j]))] = 1 / max(rows[names[i]], rows[names[j]])
    for _ in range(rng.randint(0, n)):
        a, b = rng.sample(names, 2)
        selectivity.setdefault(frozenset((a, b)), rng.choice([0.5, 0.1, 0.01, 0.001]))
    return rows, selectivity


@pytest.mark.problem("13.2")
@pytest.mark.parametrize("n", [2, 3, 4, 5, 6])
def test_problem_13_2_no_order_is_cheaper_than_yours(n):
    rng = random.Random(1300 + n)
    for _ in range(20):
        rows, selectivity = instance(rng, n)
        yours = best_order(dict(rows), dict(selectivity))
        assert sorted(yours) == sorted(rows), f"your order {yours} does not join each table once"
        mine = cost(yours, rows, selectivity)
        assert mine is not None, f"in {yours}, a table has no condition with any table before it"
        best = min(c for p in itertools.permutations(rows) if (c := cost(p, rows, selectivity)) is not None)
        assert mine <= best * (1 + 1e-9), (
            f"{yours} hands up {mine:,.0f} rows; the best order hands up {best:,.0f}"
        )


@pytest.mark.problem("13.2")
def test_problem_13_2_the_chapters_three_tables():
    rows = {"orders": 20_000, "customers": 1000, "countries": 2}
    selectivity = {
        frozenset(("orders", "customers")): 1 / 1000,
        frozenset(("customers", "countries")): 1 / 12,
    }
    assert best_order(rows, selectivity)[:2] in (["customers", "countries"], ["countries", "customers"])


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        histogram([1.0, 2.0], 1)
    with pytest.raises(NotImplementedError):
        fraction_above([0.0, 1.0], 0.5)
    with pytest.raises(NotImplementedError):
        best_order({"a": 1, "b": 1}, {frozenset(("a", "b")): 1.0})


def test_the_graders_expectations_can_be_computed():
    assert len(amounts()) > 0
    assert cost(["a", "b"], {"a": 2, "b": 3}, {frozenset(("a", "b")): 0.5}) == 3.0
