"""Graders for ch14's problems. Each expected answer is derived at test time: from the files'
footers, the book's simulated workers, or DuckDB. None is stored."""

from __future__ import annotations

import random
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from parallelism_on_one_machine import local_top, merge_tops, split

from query_lab.parallel import assign
from query_lab.reference import connect

ROOT = Path(__file__).resolve().parents[2]
SHUFFLED = ROOT / "fixtures" / "orders-shuffled.parquet"


def row_groups(name: str) -> list[int]:
    md = pq.ParquetFile(ROOT / "fixtures" / name).metadata
    return [md.row_group(i).num_rows for i in range(md.num_row_groups)]


def check_split(groups: list[int], most: int) -> list[tuple[int, int, int]]:
    morsels = split(list(groups), most)
    covered = {g: [] for g in range(len(groups))}
    for g, first, rows in morsels:
        assert 0 < rows <= most, f"a morsel of {rows} rows, with at most {most} allowed"
        covered[g].append((first, rows))
    for g, spans in covered.items():
        position = 0
        for first, rows in sorted(spans):
            assert first == position, f"row group {g}: rows from {position} are missing or repeated"
            position += rows
        assert position == groups[g], f"row group {g}: {position} of its {groups[g]} rows are covered"
    assert len(morsels) == sum(-(-n // most) for n in groups), "more morsels than the rules need"
    return morsels


# Problem 14.1 ----------------------------------------------------------------------------------


@pytest.mark.problem("14.1")
@pytest.mark.parametrize("most", [1, 999, 1000, 2000, 7000, 50_000])
def test_problem_14_1_the_morsels_cover_every_row_once(most):
    for name in ("orders-sorted.parquet", "orders-paged.parquet"):
        check_split(row_groups(name), most)
    rng = random.Random(14)
    for _ in range(50):
        check_split([rng.randint(0, 5000) for _ in range(rng.randint(1, 8))], rng.randint(1, 3000))


@pytest.mark.problem("14.1")
def test_problem_14_1_one_row_group_now_keeps_four_workers_busy():
    morsels = check_split(row_groups("orders-paged.parquet"), 1000)
    work = [rows for _, _, rows in morsels]
    owner = assign(work, 4)
    busiest = max(sum(w for w, o in zip(work, owner, strict=True) if o == k) for k in range(4))
    assert sum(work) / busiest >= 3.9


# Problem 14.2 ----------------------------------------------------------------------------------


@pytest.mark.problem("14.2")
@pytest.mark.parametrize("k", [1, 10, 100, 3000])
@pytest.mark.parametrize("workers", [1, 3, 4, 16])
def test_problem_14_2_the_merged_tops_are_duckdbs(k, workers):
    table = pq.read_table(SHUFFLED, columns=["amount", "order_id"])
    rows = list(zip(table.column("amount").to_pylist(), table.column("order_id").to_pylist(), strict=True))
    morsels = [rows[i : i + 2000] for i in range(0, len(rows), 2000)]
    owner = assign([len(m) for m in morsels], workers)
    tops = []
    for w in range(workers):
        mine = [r for m, o in zip(morsels, owner, strict=True) if o == w for r in m]
        top = local_top(mine, k)
        assert len(top) <= k, f"a worker kept {len(top)} rows, with k = {k}"
        tops.append(top)
    want = (
        connect()
        .execute(f"SELECT amount, order_id FROM '{SHUFFLED}' ORDER BY amount DESC, order_id LIMIT {k}")
        .fetchall()
    )
    assert merge_tops(tops, k) == want


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        split([10], 5)
    with pytest.raises(NotImplementedError):
        local_top([(1.0, 1)], 1)
    with pytest.raises(NotImplementedError):
        merge_tops([[(1.0, 1)]], 1)


def test_the_graders_expectations_can_be_computed():
    assert sum(row_groups("orders-paged.parquet")) == sum(row_groups("orders-sorted.parquet"))
    assert assign([1, 1, 1], 2) == [0, 1, 0]
