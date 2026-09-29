"""Graders for ch10's problems. Each expected answer is derived at test time, by running the
book's external sort on batches of the sizes the problem gives. None is stored."""

from __future__ import annotations

import random

import pyarrow as pa
import pytest
from memory_limits_and_spilling import merge_plan, runs_for

from query_lab.operators import Operator
from query_lab.spill import ExternalSort

WIDTH = 8
"""The bytes of one row of the graders' batches: one 64-bit integer, no nulls."""


class Batches(Operator):
    """A child that hands up batches of the given sizes in bytes, whole rows of eight bytes."""

    def __init__(self, sizes: list[int], seed: int = 0) -> None:
        super().__init__("Batches", "the grader's", [])
        rng = random.Random(seed)
        self.made = [
            pa.RecordBatch.from_arrays(
                [pa.array([rng.randrange(10**6) for _ in range(size // WIDTH)], pa.int64())], ["v"]
            )
            for size in sizes
        ]

    def batches(self):
        for batch in self.made:
            yield self.emit(batch)

    def schema(self):
        return pa.schema([("v", pa.int64())])


def book_sort(sizes: list[int], memory_limit: int, fan_in: int = 8) -> ExternalSort:
    op = ExternalSort(Batches(sizes), [("v", False)], memory_limit, fan_in)
    rows = op.run().column("v").to_pylist()
    assert rows == sorted(rows)
    return op


def batches_per_run(sizes: list[int], rows_per_run: list[int]) -> list[int]:
    """The book's runs, from rows to batches."""
    out, i = [], 0
    for rows in rows_per_run:
        n = 0
        while rows > 0:
            rows -= sizes[i] // WIDTH
            i += 1
            n += 1
        out.append(n)
    return out


# Problem 10.1 ----------------------------------------------------------------------------------


@pytest.mark.problem("10.1")
def test_problem_10_1_the_runs_are_the_books():
    rng = random.Random(10)
    for _ in range(60):
        sizes = [WIDTH * rng.randint(1, 40) for _ in range(rng.randint(1, 30))]
        limit = WIDTH * rng.randint(1, 120)
        op = book_sort(sizes, limit)
        want = batches_per_run(sizes, op.run_rows) if op.run_rows else [len(sizes)]
        got = runs_for(list(sizes), limit)
        assert got == want, f"batches {sizes} within {limit} bytes: you cut {got}, the sort cut {want}"


@pytest.mark.problem("10.1")
def test_problem_10_1_a_batch_larger_than_memory_is_a_run_alone():
    assert runs_for([80, 800, 80], 100) == batches_per_run(
        [80, 800, 80], book_sort([80, 800, 80], 100).run_rows
    )


# Problem 10.2 ----------------------------------------------------------------------------------


@pytest.mark.problem("10.2")
@pytest.mark.parametrize("fan_in", [2, 3, 4, 8])
def test_problem_10_2_the_merges_are_the_books(fan_in):
    for runs in range(0, 40):
        # Each batch larger than the limit: a run per batch.
        op = book_sort([WIDTH * 4] * runs, WIDTH, fan_in)
        want = (op.passes, op.merged_runs)
        assert merge_plan(runs, fan_in) == want, f"{runs} runs, fan-in {fan_in}: the sort made {want}"


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        runs_for([8], 8)
    with pytest.raises(NotImplementedError):
        merge_plan(3, 2)


def test_the_graders_expectations_can_be_computed():
    op = book_sort([WIDTH * 4] * 5, WIDTH, 2)
    assert op.sorted_runs == 5 and op.passes > 1
