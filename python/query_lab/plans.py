"""Plans written by hand, one for each query in ``queries/`` that the engine runs (ch01, ch02).

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

from .cache import Cache
from .memory import fixed_width_array, gather
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


def in_date_order(table: pa.Table) -> list[int]:
    """The positions of ``table``'s rows in the order ``ORDER BY order_date, order_id`` puts them.

    Finding the order is a sort, and sorting is Part III's. pyarrow's sort finds it here, so ch02
    can measure the part that follows: moving every row to its place.
    """
    keys = [("order_date", "ascending"), ("order_id", "ascending")]
    return pc.sort_indices(table, keys).to_pylist()


#: The columns queries/orders_by_date.sql reads, as its SELECT lists them.
ORDERS_BY_DATE = ["order_id", "order_date", "status", "amount", "note"]


def orders_by_date(root: Path, fixture: str = "orders-shuffled.parquet") -> tuple[pa.Table, dict[str, Cache]]:
    """queries/orders_by_date.sql by hand: read the columns, find the date order, then gather each
    column into that order through a cache of its own. Returns the result, and each column's cache.

    ``file_row_number`` is the position each row came from, which is the order itself.
    """
    table = Scan(root / "fixtures" / fixture, ORDERS_BY_DATE).run()
    order = in_date_order(table)
    columns = {"file_row_number": fixed_width_array(order, pa.int64())}
    caches = {}
    for name in ORDERS_BY_DATE:
        caches[name] = Cache()
        # The whole column as one array: a sort needs every row before it can place the first.
        columns[name] = gather(table.column(name).combine_chunks(), order, caches[name])
    return pa.table(columns), caches


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
