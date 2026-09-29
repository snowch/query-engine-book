"""Problems for ch10, Memory limits and spilling. Replace each ``raise NotImplementedError`` with
your answer, then press Run the graders.
"""

from __future__ import annotations


def runs_for(batch_bytes: list[int], memory_limit: int) -> list[int]:
    """Problem 10.1: how the external sort cuts its input into sorted runs.

    ``batch_bytes`` are the sizes of the batches the sort's child hands up, in order. The sort
    holds batches until the next one would take it over ``memory_limit`` bytes; then it sorts
    what it holds into a run, spills it, and starts again with that next batch. A batch larger
    than the limit is held alone, and makes a run of its own. Return the number of batches in
    each run, in order. Every batch is in exactly one run.
    """
    raise NotImplementedError("problem 10.1: cut the runs")


def merge_plan(runs: int, fan_in: int) -> tuple[int, int]:
    """Problem 10.2: the merges an external sort makes, as ``(passes, runs written)``.

    While there are more runs than ``fan_in``, a pass merges them ``fan_in`` at a time, first to
    last (the last group may be smaller), and writes each group's merge to temporary storage as
    a new run. Once no more than ``fan_in`` runs are left, one last pass merges them all and hands
    the rows up, writing nothing. With one run or none, the sort spilled nothing and merges
    nothing: ``(0, 0)``. Otherwise count every pass, the last one included, and every run the
    passes before it wrote.
    """
    raise NotImplementedError("problem 10.2: plan the merges")
