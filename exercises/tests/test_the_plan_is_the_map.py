"""Graders for ch01's problems. Each expected answer is derived at test time, from DuckDB or from
the fixture's own metadata, never stored."""

from __future__ import annotations

import math
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest
from the_plan_is_the_map import Limit, customer_orders

from query_lab.operators import Filter, Scan
from query_lab.reference import connect

ROOT = Path(__file__).resolve().parents[2]
SORTED = ROOT / "fixtures" / "orders-sorted.parquet"


def duckdb_rows(sql: str) -> list[tuple]:
    return connect().execute(sql.replace("ORDERS", f"read_parquet('{SORTED}')")).fetchall()


def group_sizes() -> list[int]:
    md = pq.ParquetFile(SORTED).metadata
    return [md.row_group(i).num_rows for i in range(md.num_row_groups)]


def batches_needed(rows_per_batch: list[int], n: int) -> int:
    """The fewest batches, taken in order, that hold ``n`` rows (all of them if there are fewer)."""
    if n == 0:
        return 0
    total = 0
    for i, rows in enumerate(rows_per_batch):
        total += rows
        if total >= n:
            return i + 1
    return len(rows_per_batch)


# Problem 1.1 -----------------------------------------------------------------------------------

LIMITS = [0, 1, 7, 1999, 2000, 2001, 4500, 19999, 20000, 25000]


@pytest.mark.problem("1.1")
@pytest.mark.parametrize("n", LIMITS)
def test_problem_1_1_a_limit_returns_duckdbs_first_rows(n):
    plan = Limit(Scan(SORTED, ["order_id", "amount"]), n)
    got = [tuple(r.values()) for r in plan.run().to_pylist()]
    assert got == duckdb_rows(f"SELECT order_id, amount FROM ORDERS LIMIT {n}")
    plan.metrics.check()


@pytest.mark.problem("1.1")
@pytest.mark.parametrize("n", LIMITS)
def test_problem_1_1_a_limit_stops_asking_once_it_has_enough(n):
    scan = Scan(SORTED, ["order_id"])
    plan = Limit(scan, n)
    plan.run()
    want = batches_needed(group_sizes(), n)
    assert scan.metrics.batches_out == want, (
        f"the scan produced {scan.metrics.batches_out} batches for a limit of {n}; it needed "
        f"{want}. A limit stops pulling from its child once it holds n rows."
    )
    assert plan.metrics.rows_out == min(n, sum(group_sizes()))


@pytest.mark.problem("1.1")
def test_problem_1_1_a_limit_above_a_filter_pulls_only_what_it_needs():
    scan = Scan(SORTED, ["order_id", "status"])
    returned = Filter(scan, "status = 'returned'", lambda b: pc.equal(b["status"], "returned"))
    plan = Limit(returned, 250)
    got = [tuple(r.values()) for r in plan.run().to_pylist()]
    assert got == duckdb_rows("SELECT order_id, status FROM ORDERS WHERE status = 'returned' LIMIT 250")
    # How many returned orders each row group holds, from the file itself.
    table = pq.read_table(SORTED, columns=["status"])
    per_group, start = [], 0
    for rows in group_sizes():
        per_group.append(pc.sum(pc.equal(table["status"].slice(start, rows), "returned")).as_py())
        start += rows
    assert scan.metrics.batches_out == batches_needed(per_group, 250)
    plan.metrics.check()


# Problem 1.2 -----------------------------------------------------------------------------------


@pytest.mark.problem("1.2")
@pytest.mark.parametrize("customer_id", [1, 2, 17, 500, 999])
def test_problem_1_2_your_plan_returns_duckdbs_rows(customer_id):
    plan = customer_orders(ROOT, customer_id)
    got = [tuple(r.values()) for r in plan.run().to_pylist()]
    want = duckdb_rows(f"SELECT order_id, order_date, amount FROM ORDERS WHERE customer_id = {customer_id}")
    assert got == want
    assert plan.schema().names == ["order_id", "order_date", "amount"]
    plan.metrics.check()


@pytest.mark.problem("1.2")
def test_problem_1_2_your_plan_reads_only_the_columns_it_needs():
    plan = customer_orders(ROOT, 17)
    plan.run()
    scans = [m for m in plan.metrics.walk() if m.operator == "Scan"]
    assert len(scans) == 1, "one scan of the orders"
    for column in ("note", "status", "quantity"):
        assert f" {column}" not in scans[0].detail and f":{column}" not in scans[0].detail, (
            f"the scan reads {column}, which the query never uses"
        )


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        list(Limit(Scan(SORTED, ["order_id"]), 5).batches())
    with pytest.raises(NotImplementedError):
        customer_orders(ROOT, 17)


def test_the_graders_expectations_can_be_computed():
    assert batches_needed(group_sizes(), 0) == 0
    assert batches_needed(group_sizes(), sum(group_sizes()) + 1) == len(group_sizes())
    assert math.ceil(2001 / group_sizes()[0]) == batches_needed(group_sizes(), 2001)
    assert duckdb_rows("SELECT count(*) FROM ORDERS WHERE customer_id = 17")[0][0] > 0
