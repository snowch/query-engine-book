"""Problems for ch13, Statistics, cost and join order. Replace each ``raise NotImplementedError``
with your answer, then press Run the graders.
"""

from __future__ import annotations


def histogram(sample: list[float], buckets: int) -> list[float]:
    """Problem 13.1, part one: the bounds of an equal-depth histogram of ``sample``.

    Return ``buckets + 1`` bounds, smallest first: the sample's smallest value, then the values
    below which a quarter, a half and so on of the sample falls (for four buckets), then its
    largest value. Each bucket then holds about the same number of the sample's values, however
    they are spread.
    """
    raise NotImplementedError("problem 13.1: build the histogram")


def fraction_above(bounds: list[float], x: float) -> float:
    """Problem 13.1, part two: the fraction of values above ``x``, estimated from ``bounds``.

    Each bucket holds the same share of the values. Count the whole share of every bucket above
    ``x``; in the bucket ``x`` falls in, count the part above ``x`` as if its values were spread
    evenly between its bounds. Below the smallest bound the answer is one, above the largest nought.
    """
    raise NotImplementedError("problem 13.1: estimate from the histogram")


def best_order(rows: dict[str, int], selectivity: dict[frozenset, float]) -> list[str]:
    """Problem 13.2: the order to join tables in, one at a time, that hands up the fewest rows.

    ``rows`` gives each table's rows. ``selectivity`` gives, for each pair of tables a condition
    joins, the fraction of the pairs of their rows it keeps; a pair missing from it has no
    condition. A set of tables joined together hands up the product of their rows and of the
    selectivities of every pair among them. Join the tables in the order you return: the second
    to the first, the third to those two, and so on. Each table after the first must have a
    condition with some table before it. Return the order whose joins hand up the fewest rows,
    added together over every join.
    """
    raise NotImplementedError("problem 13.2: choose the order")
