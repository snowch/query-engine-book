"""Plans written by hand, one for each query in ``queries/`` that the engine runs (ch01 to ch06).

The engine has no planner yet: that is Part IV. Until then, each query the book runs through
the engine has a plan here, built from operators the way DuckDB's ``EXPLAIN`` drew its own,
and registered under the query's file name so the figures, the tests and the command line find
it from the query.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from functools import partial
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc

from .cache import Cache
from .expressions import Call, Column, Literal, evaluate
from .memory import fixed_width_array, gather
from .operators import Comparison, Filter, Operator, Project, Scan, TableScan
from .storage import ComputingStore, StorageScan


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


#: Every column of the orders files, in the order the generator writes them.
ORDERS_COLUMNS = ["order_id", "order_date", "customer_id", "status", "quantity", "amount", "note"]

#: queries/early_march.sql's predicates, as a scan tests them.
EARLY_MARCH = [
    Comparison("order_date", ">=", dt.date(2024, 3, 1)),
    Comparison("order_date", "<", dt.date(2024, 3, 15)),
]


def early_march(root: Path, fixture: str = "orders-sorted.parquet") -> Operator:
    """queries/early_march.sql with both predicates pushed into the scan: the whole plan is the
    scan, as DuckDB's is. ``fixture`` runs the same query against another orders file."""
    return Scan(root / "fixtures" / fixture, ["order_id", "customer_id", "amount"], filters=EARLY_MARCH)


def early_march_by_page(root: Path, fixture: str = "orders-paged.parquet") -> Operator:
    """queries/early_march_paged.sql: chapter 3's scan, told to use the page index (ch04). On a
    file without one, it reads by row group, as chapter 3's did."""
    columns = ["order_id", "customer_id", "amount"]
    return Scan(root / "fixtures" / fixture, columns, filters=EARLY_MARCH, page_index=True)


def early_march_table(root: Path, metadata: bool = True) -> Operator:
    """queries/early_march_table.sql: the fortnight from the table of monthly files (ch05). With
    ``metadata``, the scan reads the table's metadata first; without it, it opens every file."""
    columns = ["order_id", "customer_id", "amount"]
    return TableScan(root / "fixtures" / "orders-by-month", columns, filters=EARLY_MARCH, metadata=metadata)


def early_march_in_storage(root: Path, fixture: str = "orders-sorted.parquet") -> Operator:
    """chapter 3's scan handed to the storage (ch05): the storage tests the dates and sends back
    only the rows that pass."""
    columns = ["order_id", "customer_id", "amount"]
    return StorageScan(ComputingStore(root / "fixtures"), fixture, columns, filters=EARLY_MARCH)


#: Scans a panel can set side by side under a name, where one query file cannot say which (ch05).
SCANS: dict[str, Callable[[Path], Operator]] = {
    "by its metadata": lambda root: early_march_table(root, metadata=True),
    "by its files": lambda root: early_march_table(root, metadata=False),
}


def early_march_above(root: Path, fixture: str, columns: list[str]) -> Operator:
    """queries/early_march.sql with nothing pushed into the scan but ``columns``: the scan hands
    up every row of every row group, and a filter above it tests the dates, as ch01's plan did."""
    scan = Scan(root / "fixtures" / fixture, columns)
    march = Filter(scan, " AND ".join(map(str, EARLY_MARCH)), _all(EARLY_MARCH))
    return Project(march, {name: _column(name) for name in ["order_id", "customer_id", "amount"]})


def _all(comparisons: list[Comparison]):
    """A filter's predicate: true where every comparison is."""

    def predicate(batch: pa.RecordBatch) -> pa.Array:
        masks = [c.mask(batch) for c in comparisons]
        out = masks[0]
        for m in masks[1:]:
            out = pc.and_(out, m)
        return out

    return predicate


def _column(name: str):
    return lambda batch: batch[name]


def largest_orders(root: Path, fixture: str = "orders-sorted.parquet") -> Operator:
    """queries/largest_orders.sql, its predicate pushed into the scan."""
    return Scan(
        root / "fixtures" / fixture, ["order_id", "amount"], filters=[Comparison("amount", ">", 2400.0)]
    )


#: The expressions of queries/with_tax.sql, as trees (ch06). The engine has no parser yet, so
#: they are written out here, exactly as the query writes them.
WITH_TAX_WHERE = Call(
    "and",
    (
        Call(">", (Call("/", (Column("amount"), Column("quantity"))), Call("*", (Literal(50), Literal(2))))),
        Call(">", (Call("+", (Column("quantity"), Literal(1))), Literal(3))),
    ),
)
WITH_TAX = Call("*", (Column("amount"), Call("+", (Literal(1), Call("/", (Literal(20), Literal(100)))))))


def with_tax(root: Path) -> Operator:
    """queries/with_tax.sql, operator by operator, each expression evaluated as a tree a batch at
    a time, as the query writes it: there is no planner yet to rewrite it (ch06)."""
    scan = Scan(root / "fixtures" / "orders-sorted.parquet", ["order_id", "amount", "quantity"])
    kept = Filter(scan, str(WITH_TAX_WHERE), partial(evaluate, WITH_TAX_WHERE))
    return Project(
        kept, {"order_id": partial(evaluate, Column("order_id")), "with_tax": partial(evaluate, WITH_TAX)}
    )


#: Each plan, by the query file it answers.
PLANS: dict[str, Callable[[Path], Operator]] = {
    "returned_unit_price.sql": returned_unit_price,
    "early_march.sql": early_march,
    "early_march_paged.sql": early_march_by_page,
    "early_march_table.sql": early_march_table,
    "largest_orders.sql": largest_orders,
    "with_tax.sql": with_tax,
}

#: For each plan, the DuckDB operator that does the same job as each of the plan's operators,
#: top down, or None where DuckDB has no operator of its own for it. DuckDB tests
#: ``status = 'returned'`` inside its scan, so its scan's output is the output of this plan's
#: first filter, and this plan's scan has no partner. tests/test_operators.py requires each pair
#: to produce the same rows.
DUCKDB_PARTNERS: dict[str, list[str | None]] = {
    "returned_unit_price.sql": ["PROJECTION", "FILTER", "TABLE_SCAN", None],
    "early_march.sql": ["TABLE_SCAN"],
    "early_march_paged.sql": ["TABLE_SCAN"],
    "early_march_table.sql": ["TABLE_SCAN"],
    "largest_orders.sql": ["TABLE_SCAN"],
    "with_tax.sql": ["PROJECTION", "FILTER", None],
}


def plan_for(root: Path, query: str) -> Operator:
    if query not in PLANS:
        raise KeyError(f"no hand-written plan for queries/{query}; the plans are {', '.join(PLANS)}")
    return PLANS[query](root)
