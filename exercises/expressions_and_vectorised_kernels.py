"""Problems for ch06, Expressions and vectorised kernels. Replace each ``raise NotImplementedError``
with your answer, then press Run the graders.
"""

from __future__ import annotations

from query_lab.expressions import (  # noqa: F401  (you will want them)
    SCALARS,
    Call,
    Column,
    Expression,
    Literal,
)


def fold(expr: Expression) -> Expression:
    """Problem 6.1: the same expression with every part that depends on no column computed once,
    before any row is seen, and replaced by a ``Literal`` of its value.

    ``expr`` is a tree of ``Column``, ``Literal`` and ``Call`` nodes, as ``query_lab.expressions``
    defines them: a ``Call`` has an ``op`` (``+``, ``-``, ``*``, ``/``, a comparison, ``and`` or
    ``or``) and a tuple of ``args``, each an expression. ``SCALARS[op]`` applies an operator to
    single values. Return a new tree; leave ``expr`` as it was. A part that does depend on a
    column stays a ``Call``, with its arguments folded in turn.
    """
    raise NotImplementedError("problem 6.1: fold the constants")


def always_wrong(n: int, start: int) -> list[bool]:
    """Problem 6.2: ``n`` outcomes of one branch, ``True`` for taken, that the book's two-bit
    predictor gets wrong every time, starting from the counter ``start``.

    The predictor keeps a counter from 0 to 3 for the branch. It predicts taken when the counter
    is 2 or 3; then it moves the counter one step up if the branch was taken and one step down if
    not, never below 0 or above 3. The book's predictor starts every branch at 1; here ``start``
    may be any of the four.
    """
    raise NotImplementedError("problem 6.2: which outcomes?")
