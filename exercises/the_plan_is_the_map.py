"""Problems for ch01, The plan is the map. Replace each ``raise NotImplementedError`` with your
answer, then press Run the graders.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow.compute as pc  # noqa: F401  (you will want it)

from query_lab.operators import Filter, Operator, Project, Scan  # noqa: F401


def customer_orders(root: Path, customer_id: int) -> Operator:
    """Problem 1.1: the plan, built from the book's operators, for

        SELECT order_id, order_date, amount
        FROM 'fixtures/orders-sorted.parquet'
        WHERE customer_id = <customer_id>

    ``root`` is the repository's root; the file is ``root / "fixtures" / "orders-sorted.parquet"``.
    Read only the columns the query needs. Return the plan's top operator; do not run it.
    """
    raise NotImplementedError("problem 1.1: a plan of your own")


def expected_rows(rows: int, status_share: float, low: float, high: float, threshold: float) -> float:
    """Problem 1.2: the rows the chapter's query keeps, worked out from the orders' recipe.

    The generator wrote ``rows`` orders. A ``status_share`` of them have the status the query
    asks for, and each order's unit price was drawn evenly between ``low`` and ``high``, whatever
    its status. Return how many rows you expect the query to keep: those with the status whose
    unit price is over ``threshold``. The planner could not work this out, since nobody gave it
    the recipe; you can.
    """
    raise NotImplementedError("problem 1.2: work out the rows")
