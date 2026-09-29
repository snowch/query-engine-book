"""Problems for ch12, Optimiser rules. Replace each ``raise NotImplementedError`` with your answer,
then press Run the graders.
"""

from __future__ import annotations

from query_lab.expressions import Expression
from query_lab.planner import Node


def move_constants(condition: Expression) -> Expression:
    """Problem 12.1: a comparison rewritten so that a column stands alone on one side.

    ``quantity + 1 > 3`` compares an expression with a constant, and a scan cannot test it; the
    same condition as ``quantity > 2`` compares a column with a constant, and it can. Where
    ``condition`` compares a column plus or minus a constant (on either side of the ``+``) with
    another constant, return the comparison of the column alone with the constant the other side
    becomes. Rewrite inside ``and``, ``or`` and ``not`` too. Return anything else as it is: the
    answer must be true for exactly the rows the condition was true for.
    """
    raise NotImplementedError("problem 12.1: move the constants")


def across_the_join(node: Node) -> Node:
    """Problem 12.2: a rule that copies a condition on one side's join key to the other side's.

    Below a join on ``o.customer_id = c.customer_id``, the two keys are equal in every row the
    join hands up, so a condition that compares one of them with a constant holds for the other
    as well. For every filter directly above a join, return the plan with each part of its
    condition (the parts joined by ``AND``) that compares one of that join's keys with a
    constant also asked of the other key, so that ch12's ``push_filters``, run after your rule,
    can test each copy in its own table's scan. Change nothing else.
    """
    raise NotImplementedError("problem 12.2: carry the condition across")
