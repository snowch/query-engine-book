"""Problems for ch03, Projection and filter pushdown. Replace each ``raise NotImplementedError``
with your answer, then press Run the graders.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc  # noqa: F401  (you may want it)

from query_lab.operators import Comparison, Filter, Operator, Project, Scan  # noqa: F401
from query_lab.plans import unit_price  # noqa: F401  (you will want it)


def could_match(op: str, value: object, low: object, high: object) -> bool:
    """Problem 3.1: whether some value between ``low`` and ``high``, both included, could satisfy
    ``column op value``.

    ``op`` is one of ``=``, ``!=``, ``<``, ``<=``, ``>``, ``>=``. ``low`` and ``high`` are a
    row group's smallest and largest value of the column, from its statistics: ints, floats,
    dates or strings, each comparable with ``value``. Return False only when no value in the
    range could satisfy the comparison, so a scan may skip the row group: a wrong False loses
    rows. Return True otherwise, but no more often than you must: a wrong True reads a row group
    for nothing, and the graders count those.

    The graders refuse the book's own statistics test (``Comparison.against_statistics`` and the
    Parquet book's ``against_bounds``).
    """
    raise NotImplementedError("problem 3.1: could it match?")


def returned_unit_price_pushed(root: Path) -> Operator:
    """Problem 3.2: ch01's plan for queries/returned_unit_price.sql, with ``status = 'returned'``
    pushed into the scan, as DuckDB pushes it.

    The scan tests the status and hands up only the rows that pass, without the ``status``
    column, which nothing above it needs. The unit price test stays in a filter above the scan,
    and a projection computes the result. ``root`` is the repository's root; the file is
    ``root / "fixtures" / "orders-sorted.parquet"``. Return the plan's top operator; do not run it.
    """
    raise NotImplementedError("problem 3.2: push the status test into the scan")


class Limit(Operator):
    """Problem 3.3: pass on the first ``n`` rows the child produces, and no more.

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
        raise NotImplementedError("problem 3.3: a limit")

    def schema(self) -> pa.Schema:
        return self.child.schema()
