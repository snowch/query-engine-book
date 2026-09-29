"""Problems for ch09, Sorting and top-k. Replace each ``raise NotImplementedError`` with your
answer, then press Run the graders.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator


def merge_runs(runs: list[Iterable]) -> Iterator:
    """Problem 9.1: yield every value of ``runs``, each already sorted in ascending order, as one
    ascending sequence: the last step of a sort too large for memory, which sorts runs that fit
    and then merges them.

    Yield as you go, and never take a value from a run before you need it: hold at most one
    value from each run at a time, so the merge needs memory for one value per run, however long
    the runs are. Where two runs hold equal values, yield the one from the earlier run first.
    """
    raise NotImplementedError("problem 9.1: merge the runs")


def top_per_customer(rows: list[tuple[int, int, float]], k: int) -> dict[int, list[int]]:
    """Problem 9.2: each customer's ``k`` largest orders.

    ``rows`` are ``(customer_id, order_id, amount)``. Return a dict mapping each customer to the
    order ids of their ``k`` largest orders by amount, largest first, ties broken by the smaller
    order id first. A customer with fewer than ``k`` orders keeps them all. Keep no more than
    ``k`` orders per customer at any time.
    """
    raise NotImplementedError("problem 9.2: the top k of each customer")
