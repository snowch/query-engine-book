"""Graders for ch07's problems. Each expected answer is derived at test time: from the book's
hash table, or from DuckDB over the whole file. None is stored."""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from hash_aggregation import combine, probes

from query_lab import aggregate
from query_lab.aggregate import HashTable
from query_lab.reference import connect

ROOT = Path(__file__).resolve().parents[2]
SORTED = ROOT / "fixtures" / "orders-sorted.parquet"


class KnownHash:
    """A key whose hash the grader chooses, so the book's table probes exactly as for ``h``."""

    def __init__(self, h: int) -> None:
        self.h = h


def book_probes(hashes: list[int], capacity: int, monkeypatch) -> int:
    """What the book's table probes for these hashes, with the hashing and the growth set aside."""
    with monkeypatch.context() as m:
        m.setattr(aggregate, "hash_key", lambda key: key.h)
        m.setattr(aggregate, "LOAD", 1.0)
        table = HashTable(capacity=capacity)
        for h in hashes:
            table.find(KnownHash(h))
    return table.probes


def cases():
    rng = random.Random(7)
    out = [([0, 0, 0, 0], 8), ([7, 7, 7], 8), ([5, 13, 21], 8), ([1, 2, 3], 4)]
    for _ in range(80):
        capacity = 1 << rng.randint(2, 9)
        n = rng.randint(1, capacity - 1)
        spread = rng.choice([capacity, capacity * 1000, 3])
        out.append(([rng.randrange(spread) for _ in range(n)], capacity))
    return out


# Problem 7.1 -----------------------------------------------------------------------------------


@pytest.mark.problem("7.1")
def test_problem_7_1_probes_match_the_books_table(monkeypatch):
    for hashes, capacity in cases():
        want = book_probes(hashes, capacity, monkeypatch)
        got = probes(list(hashes), capacity)
        assert got == want, (
            f"hashes {hashes[:8]}... into {capacity} slots: you count {got}, the table probes {want}"
        )


@pytest.mark.problem("7.1")
def test_problem_7_1_a_full_run_of_one_hash_probes_a_triangle(monkeypatch):
    for n in (1, 2, 5, 31):
        assert probes([3] * n, 32) == n * (n + 1) // 2 == book_probes([3] * n, 32, monkeypatch)


# Problem 7.2 -----------------------------------------------------------------------------------


def parts_of(sql_where: str, cuts: int):
    """The orders' amounts aggregated by customer, one part per slice of the file's rows."""
    con = connect()
    total = con.execute(f"SELECT count(*) FROM '{SORTED}'").fetchone()[0]
    step = -(-total // cuts)
    parts = []
    for i in range(cuts):
        rows = con.execute(
            f"SELECT customer_id, count(*), sum(amount), min(amount), max(amount) "
            f"FROM read_parquet('{SORTED}', file_row_number = true) "
            f"WHERE file_row_number >= {i * step} AND file_row_number < {(i + 1) * step} {sql_where} "
            "GROUP BY customer_id"
        ).fetchall()
        parts.append({r[0]: tuple(r[1:]) for r in rows})
    whole = con.execute(
        f"SELECT customer_id, count(*), sum(amount), min(amount), max(amount), avg(amount) "
        f"FROM '{SORTED}' WHERE true {sql_where} GROUP BY customer_id"
    ).fetchall()
    return parts, {r[0]: tuple(r[1:]) for r in whole}


@pytest.mark.problem("7.2")
@pytest.mark.parametrize("cuts", [1, 2, 10, 37])
def test_problem_7_2_the_parts_combine_to_duckdbs_aggregates_over_the_whole_file(cuts):
    parts, whole = parts_of("", cuts)
    got = combine(parts)
    assert set(got) == set(whole), "every customer, and no other key"
    for key, want in whole.items():
        count, total, low, high, avg = got[key]
        assert (count, low, high) == (want[0], want[2], want[3]), f"customer {key}"
        assert total == pytest.approx(want[1]) and avg == pytest.approx(want[4]), f"customer {key}"


@pytest.mark.problem("7.2")
def test_problem_7_2_a_key_missing_from_some_parts_is_still_combined():
    parts = [{"a": (2, 10.0, 4.0, 6.0)}, {}, {"a": (1, 1.0, 1.0, 1.0), "b": (1, 7.0, 7.0, 7.0)}]
    got = combine(parts)
    assert got["a"][:4] == (3, 11.0, 1.0, 6.0) and got["a"][4] == pytest.approx(11.0 / 3)
    assert got["b"] == (1, 7.0, 7.0, 7.0, 7.0)
    assert combine([]) == {}


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        probes([1, 2], 4)
    with pytest.raises(NotImplementedError):
        combine([{}])


def test_the_graders_expectations_can_be_computed(monkeypatch):
    assert book_probes([0, 0, 0], 8, monkeypatch) == 6
    parts, whole = parts_of("", 3)
    assert len(parts) == 3 and len(whole) > 0
