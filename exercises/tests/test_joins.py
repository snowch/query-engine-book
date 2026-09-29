"""Graders for ch08's problems. Each expected answer is derived at test time: from DuckDB, which
joins the same rows, and from the arithmetic of a Bloom filter. None is stored."""

from __future__ import annotations

import math
import random
from pathlib import Path

import pyarrow as pa
import pytest
from joins import bloom, merge_join, might_contain

from query_lab.reference import connect

ROOT = Path(__file__).resolve().parents[2]
ORDERS = ROOT / "fixtures" / "orders-sorted.parquet"
CUSTOMERS = ROOT / "fixtures" / "customers.parquet"


def duckdb_join(left: list[tuple], right: list[tuple]) -> list[tuple]:
    """DuckDB's inner join of the two sides, in the order the problem asks for: by key, then by
    each row's place in its own side."""
    con = connect()
    for name, rows in (("l", left), ("r", right)):
        table = pa.table(
            {
                "k": [k for k, _ in rows],
                "v": [v for _, v in rows],
                "pos": list(range(len(rows))),
            }
        )
        con.register(name, table)
    return [
        tuple(row)
        for row in con.execute(
            "SELECT l.k, l.v, r.v FROM l JOIN r ON l.k = r.k ORDER BY l.k, l.pos, r.pos"
        ).fetchall()
    ]


def sides(rng: random.Random):
    left = sorted((rng.randrange(20), rng.randrange(1000)) for _ in range(rng.randrange(0, 60)))
    right = sorted((rng.randrange(20), rng.randrange(1000)) for _ in range(rng.randrange(0, 60)))
    # Sorted by key only: equal keys keep an order of their own, which the answer must keep.
    return sorted(left, key=lambda p: p[0]), sorted(right, key=lambda p: p[0])


# Problem 8.1 -----------------------------------------------------------------------------------


@pytest.mark.problem("8.1")
def test_problem_8_1_the_merge_is_duckdbs_join():
    rng = random.Random(8)
    for _ in range(60):
        left, right = sides(rng)
        want = duckdb_join(left, right)
        got = merge_join(list(left), list(right))
        assert got == want, f"left {left[:6]}..., right {right[:6]}...: {len(got)} rows, DuckDB {len(want)}"


@pytest.mark.problem("8.1")
def test_problem_8_1_the_orders_merge_with_their_customers():
    con = connect()
    orders = con.execute(
        f"SELECT customer_id, order_id FROM '{ORDERS}' ORDER BY customer_id, order_id"
    ).fetchall()
    customers = con.execute(f"SELECT customer_id, country FROM '{CUSTOMERS}' ORDER BY customer_id").fetchall()
    got = merge_join(orders, customers)
    assert got == duckdb_join(orders, customers)


@pytest.mark.problem("8.1")
def test_problem_8_1_empty_and_disjoint_sides_join_to_nothing():
    assert merge_join([], [(1, "a")]) == []
    assert merge_join([(1, "a"), (3, "b")], [(2, "c"), (4, "d")]) == []


# Problem 8.2 -----------------------------------------------------------------------------------


def enterprise_customers() -> list[int]:
    con = connect()
    return [
        r[0]
        for r in con.execute(f"SELECT customer_id FROM '{CUSTOMERS}' WHERE segment = 'enterprise'").fetchall()
    ]


@pytest.mark.problem("8.2")
@pytest.mark.parametrize("bits, hashes", [(1024, 1), (2048, 3), (4096, 4), (8192, 2)])
def test_problem_8_2_no_key_of_the_build_side_is_ever_ruled_out(bits, hashes):
    keys = enterprise_customers()
    f = bloom(keys, bits, hashes)
    assert isinstance(f, int) and 0 <= f < (1 << bits)
    assert all(might_contain(f, k, bits, hashes) for k in keys), (
        "a Bloom filter never rules out a key it holds"
    )


@pytest.mark.problem("8.2")
@pytest.mark.parametrize("bits, hashes", [(1024, 1), (2048, 3), (4096, 4), (8192, 2)])
def test_problem_8_2_other_keys_pass_about_as_often_as_the_arithmetic_says(bits, hashes):
    keys = enterprise_customers()
    f = bloom(keys, bits, hashes)
    assert bin(f).count("1") <= len(keys) * hashes
    others = [k for k in range(1001, 41_001)]
    passed = sum(might_contain(f, k, bits, hashes) for k in others) / len(others)
    expected = (1 - math.exp(-hashes * len(keys) / bits)) ** hashes
    assert 0.5 * expected <= passed <= 1.5 * expected, (
        f"{passed:.4f} of keys not in the filter pass it; with {len(keys)} keys, {bits} bits and "
        f"{hashes} hashes, about {expected:.4f} should"
    )


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        merge_join([], [])
    with pytest.raises(NotImplementedError):
        bloom([1], 64, 1)
    with pytest.raises(NotImplementedError):
        might_contain(0, 1, 64, 1)


def test_the_graders_expectations_can_be_computed():
    assert duckdb_join([(1, "a"), (1, "b")], [(1, "x")]) == [(1, "a", "x"), (1, "b", "x")]
    assert len(enterprise_customers()) > 0
