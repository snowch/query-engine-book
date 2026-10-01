"""ch01's plan for queries/returned_unit_price.sql, built from the engine's operators and run."""

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc

from query_lab.display import preview
from query_lab.operators import Filter, Project, Scan

ORDERS = Path("fixtures") / "orders-sorted.parquet"


def unit_price(batch: pa.RecordBatch) -> pa.Array:
    """amount / quantity, divided as DuckDB divides: both sides as doubles."""
    return pc.divide(batch["amount"], pc.cast(batch["quantity"], pa.float64()))


def returned_unit_price(root: Path) -> Project:
    """The plan, built bottom up, as the rows travel through it."""
    # Read the five columns the query uses, a row group at a time.
    scan = Scan(root / ORDERS, ["order_id", "customer_id", "status", "amount", "quantity"])

    # Keep the returned orders, then those whose unit price is over a hundred.
    returned = Filter(scan, "status = 'returned'", lambda b: pc.equal(b["status"], "returned"))
    pricey = Filter(returned, "amount / quantity > 100", lambda b: pc.greater(unit_price(b), 100))

    # Hand up three columns, the last of them computed.
    return Project(
        pricey,
        {
            "order_id": lambda b: b["order_id"],
            "customer_id": lambda b: b["customer_id"],
            "unit_price": unit_price,
        },
    )


if __name__ == "__main__":
    print(f"Reading {ORDERS}\n")
    plan = returned_unit_price(Path("."))
    result = plan.run()
    print(preview(result))
    print()
    print(plan.metrics)
