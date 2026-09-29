"""Problems for ch19, Compiling a query. Replace each ``raise NotImplementedError`` with your
answer, then press Run the graders.
"""

from __future__ import annotations

from dataclasses import dataclass

from query_lab.expressions import Expression


def generate_totals(filters: list[Expression], key: str, value: Expression) -> str:
    """Problem 19.1: compile a pipeline that ends in an aggregate.

    Return the source of a function ``totals(batch, sums)``. For every row of ``batch`` that
    passes every filter, in order, it adds ``value``'s value for the row to ``sums[k]``, where
    ``k`` is the row's ``key`` column, starting each new key from nought. Write one loop over the
    rows, as the chapter's compiler does, and call no kernel: ``python(expr)`` gives you Python
    for an expression's value in row ``i``, reading each column as a list named after it. The
    graders compile your source and run it with ``divide`` in its scope.
    """
    raise NotImplementedError("problem 19.1: compile the totals")


@dataclass(frozen=True)
class Parameter:
    """A constant taken out of a tree: the ``index``-th of the tree's constants."""

    index: int


def parameterise(expr: Expression) -> tuple[Expression, tuple]:
    """Problem 19.2: a tree's shape, and its constants.

    Return the tree with each ``Literal`` replaced by a ``Parameter``, numbered from nought in the
    order a walk meets them, parents before children and arguments left to right; and the
    constants' values, in the same order. Two queries that differ only in their constants then
    have the same shape, and can share one compiled function.
    """
    raise NotImplementedError("problem 19.2: take out the constants")
