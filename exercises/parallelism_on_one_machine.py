"""Problems for ch14, Parallelism on one machine. Replace each ``raise NotImplementedError`` with
your answer, then press Run the graders.
"""

from __future__ import annotations


def split(row_groups: list[int], most: int) -> list[tuple[int, int, int]]:
    """Problem 14.1: morsels of at most ``most`` rows, cut from row groups.

    ``row_groups`` gives each row group's rows, in file order. Return the morsels, each as
    ``(row group, first row within it, rows)``: every row of every row group in exactly one
    morsel, no morsel crossing from one row group into the next, none holding more than ``most``
    rows, and as few morsels as those rules allow.
    """
    raise NotImplementedError("problem 14.1: split the row groups")


def local_top(rows: list[tuple[float, int]], k: int) -> list[tuple[float, int]]:
    """Problem 14.2, part one: one worker's ``k`` largest orders among ``rows``.

    Each row is ``(amount, order_id)``. The largest amount comes first; between equal amounts, the
    smaller order id. Return at most ``k`` rows, in that order.
    """
    raise NotImplementedError("problem 14.2: one worker's top")


def merge_tops(tops: list[list[tuple[float, int]]], k: int) -> list[tuple[float, int]]:
    """Problem 14.2, part two: the ``k`` largest orders of all, from each worker's ``local_top``."""
    raise NotImplementedError("problem 14.2: merge the workers' tops")
