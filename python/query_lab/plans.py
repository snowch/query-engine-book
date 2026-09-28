"""Plans written by hand, one for each query in ``queries/`` that the engine runs (ch01).

The engine has no planner yet: that is Part IV. Until then, each query the book runs through
the engine has a plan here, built from operators the way DuckDB's ``EXPLAIN`` drew its own,
and registered under the query's file name so the figures, the tests and the command line find
it from the query.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc

from .operators import Filter, Operator, Project, Scan


def returned_unit_price(root: Path) -> Operator:
    """queries/returned_unit_price.sql, operator by operator: read, keep, keep, compute."""
    scan = Scan(
        root / "fixtures" / "orders-sorted.parquet",
        ["order_id", "customer_id", "status", "amount", "quantity"],
    )
    returned = Filter(scan, "status = 'returned'", lambda b: pc.equal(b["status"], "returned"))
    pricey = Filter(returned, "amount / quantity > 100", lambda b: pc.greater(unit_price(b), 100))
    return Project(
        pricey,
        {
            "order_id": lambda b: b["order_id"],
            "customer_id": lambda b: b["customer_id"],
            "unit_price": unit_price,
        },
    )


def unit_price(batch: pa.RecordBatch) -> pa.Array:
    """``amount / quantity``, divided as DuckDB divides: both sides as doubles."""
    return pc.divide(batch["amount"], pc.cast(batch["quantity"], pa.float64()))


#: Each plan, by the query file it answers.
PLANS: dict[str, Callable[[Path], Operator]] = {"returned_unit_price.sql": returned_unit_price}

#: For each plan, the DuckDB operator that does the same job as each of the plan's operators,
#: top down, or None where DuckDB has no operator of its own for it. DuckDB tests
#: ``status = 'returned'`` inside its scan, so its scan's output is the output of this plan's
#: first filter, and this plan's scan has no partner. tests/test_operators.py requires each pair
#: to produce the same rows.
DUCKDB_PARTNERS: dict[str, list[str | None]] = {
    "returned_unit_price.sql": ["PROJECTION", "FILTER", "TABLE_SCAN", None],
}


def plan_for(root: Path, query: str) -> Operator:
    if query not in PLANS:
        raise KeyError(f"no hand-written plan for queries/{query}; the plans are {', '.join(PLANS)}")
    return PLANS[query](root)
