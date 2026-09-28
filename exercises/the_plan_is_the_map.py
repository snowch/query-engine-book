"""Problems for ch01, The plan is the map. Replace each ``raise NotImplementedError`` with your
answer, then run the graders:

    PYTHONPATH=python:external/parquet-book/python:exercises \\
        python3 -m pytest exercises/tests/test_the_plan_is_the_map.py --problems
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc  # noqa: F401  (you will want it)

from query_lab.operators import Filter, Operator, Project, Scan  # noqa: F401


class Limit(Operator):
    """Problem 1.1: pass on the first ``n`` rows the child produces, and no more.

    Stop asking the child for batches as soon as you have ``n`` rows: the graders count the
    batches your child produced, and a limit that drains its input fails even when its result is
    right. Cut the last batch short when it holds more rows than you need. A limit of zero asks
    for nothing.

    Count what you do with ``self.take`` and ``self.emit``, as the book's operators do.
    """

    def __init__(self, child: Operator, n: int) -> None:
        super().__init__("Limit", str(n), [child])
        self.child = child
        self.n = n

    def batches(self) -> Iterator[pa.RecordBatch]:
        raise NotImplementedError("problem 1.1: a limit")

    def schema(self) -> pa.Schema:
        return self.child.schema()


def customer_orders(root: Path, customer_id: int) -> Operator:
    """Problem 1.2: the plan, built from the book's operators, for

        SELECT order_id, order_date, amount
        FROM 'fixtures/orders-sorted.parquet'
        WHERE customer_id = <customer_id>

    ``root`` is the repository's root; the file is ``root / "fixtures" / "orders-sorted.parquet"``.
    Read only the columns the query needs. Return the plan's top operator; do not run it.
    """
    raise NotImplementedError("problem 1.2: a plan of your own")
