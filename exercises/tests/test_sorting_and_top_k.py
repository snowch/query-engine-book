"""Graders for ch09's problems. Each expected answer is derived at test time: by sorting, or from
DuckDB. None is stored."""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from sorting_and_top_k import merge_runs, top_per_customer

from query_lab.reference import connect

ROOT = Path(__file__).resolve().parents[2]
ORDERS = ROOT / "fixtures" / "orders-shuffled.parquet"


class Run:
    """A sorted run that counts how many of its values have been taken."""

    def __init__(self, values: list, ledger: list[int], index: int) -> None:
        self.values, self.ledger, self.index = values, ledger, index

    def __iter__(self):
        for v in self.values:
            self.ledger[self.index] += 1
            yield v


def runs_of(rng: random.Random):
    return [
        sorted(rng.randrange(50) for _ in range(rng.randrange(0, 30))) for _ in range(rng.randrange(1, 9))
    ]


# Problem 9.1 -----------------------------------------------------------------------------------


@pytest.mark.problem("9.1")
def test_problem_9_1_the_merge_is_the_sorted_whole():
    rng = random.Random(9)
    for _ in range(80):
        runs = runs_of(rng)
        got = list(merge_runs([list(r) for r in runs]))
        assert got == sorted(v for r in runs for v in r), f"runs {runs}"


@pytest.mark.problem("9.1")
def test_problem_9_1_the_merge_takes_no_value_before_it_needs_it():
    rng = random.Random(90)
    for _ in range(40):
        runs = runs_of(rng)
        taken = [0] * len(runs)
        merged = merge_runs([Run(r, taken, i) for i, r in enumerate(runs)])
        yielded = [0] * len(runs)
        for value in merged:
            # The value came from the earliest run whose next unyielded value it is.
            source = next(i for i, r in enumerate(runs) if yielded[i] < len(r) and r[yielded[i]] == value)
            yielded[source] += 1
            ahead = [t - y for t, y in zip(taken, yielded, strict=True)]
            assert max(ahead) <= 1, f"after yielding {value}, you hold {max(ahead)} values of one run"


@pytest.mark.problem("9.1")
def test_problem_9_1_equal_values_come_from_the_earlier_run_first():
    tagged = [[(1, "a"), (2, "a")], [(1, "b"), (2, "b")]]

    class Key:
        def __init__(self, pair):
            self.pair = pair

        def __lt__(self, other):
            return self.pair[0] < other.pair[0]

        def __le__(self, other):
            return self.pair[0] <= other.pair[0]

        def __gt__(self, other):
            return self.pair[0] > other.pair[0]

        def __ge__(self, other):
            return self.pair[0] >= other.pair[0]

        def __eq__(self, other):
            return self.pair[0] == other.pair[0]

    got = [k.pair for k in merge_runs([[Key(p) for p in run] for run in tagged])]
    assert got == [(1, "a"), (1, "b"), (2, "a"), (2, "b")]


# Problem 9.2 -----------------------------------------------------------------------------------


@pytest.mark.problem("9.2")
@pytest.mark.parametrize("k", [1, 3, 10])
def test_problem_9_2_each_customers_top_orders_are_duckdbs(k):
    con = connect()
    rows = con.execute(f"SELECT customer_id, order_id, amount FROM '{ORDERS}'").fetchall()
    want: dict[int, list[int]] = {}
    for customer, order in con.execute(
        f"SELECT customer_id, order_id FROM '{ORDERS}' QUALIFY row_number() OVER "
        f"(PARTITION BY customer_id ORDER BY amount DESC, order_id) <= {k} "
        "ORDER BY customer_id, amount DESC, order_id"
    ).fetchall():
        want.setdefault(customer, []).append(order)
    got = top_per_customer(rows, k)
    assert set(got) == set(want), "every customer with an order, and no other"
    wrong = [c for c in want if got[c] != want[c]]
    assert not wrong, f"customer {wrong[0]}: you give {got[wrong[0]]}, DuckDB {want[wrong[0]]}"


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        list(merge_runs([[1]]))
    with pytest.raises(NotImplementedError):
        top_per_customer([(1, 1, 1.0)], 1)


def test_the_graders_expectations_can_be_computed():
    assert connect().execute(f"SELECT count(*) FROM '{ORDERS}'").fetchone()[0] > 0
