"""ch01's plan for queries/returned_unit_price.sql, built from the engine's operators and run."""

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc

from query_lab.display import preview
from query_lab.operators import Filter, Project, Scan


def unit_price(batch: pa.RecordBatch) -> pa.Array:
    """``amount / quantity``, divided as DuckDB divides: both sides as doubles."""
    return pc.divide(batch["amount"], pc.cast(batch["quantity"], pa.float64()))


def returned_unit_price(root: Path) -> Project:
    """The plan, bottom up: read, keep the returned orders, keep the dear ones, compute."""
    orders = root / "fixtures" / "orders-sorted.parquet"
    scan = Scan(orders, ["order_id", "customer_id", "status", "amount", "quantity"])
    returned = Filter(scan, "status = 'returned'", lambda b: pc.equal(b["status"], "returned"))
    pricey = Filter(returned, "amount / quantity > 100", lambda b: pc.greater(unit_price(b), 100))
    keep = {"order_id": lambda b: b["order_id"], "customer_id": lambda b: b["customer_id"]}
    return Project(pricey, {**keep, "unit_price": unit_price})


if __name__ == "__main__":
    plan = returned_unit_price(Path("."))
    print(preview(plan.run()), plan.metrics, sep="\n\n")
