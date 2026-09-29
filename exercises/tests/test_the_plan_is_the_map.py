"""Graders for ch01's problems. Each expected answer is derived at test time, from DuckDB or from
the fixture's own metadata, never stored."""

from __future__ import annotations

from pathlib import Path

import pytest
from the_plan_is_the_map import customer_orders, expected_rows

from query_lab.reference import connect

ROOT = Path(__file__).resolve().parents[2]
SORTED = ROOT / "fixtures" / "orders-sorted.parquet"


def duckdb_rows(sql: str) -> list[tuple]:
    return connect().execute(sql.replace("ORDERS", f"read_parquet('{SORTED}')")).fetchall()


# Problem 1.1 -----------------------------------------------------------------------------------


@pytest.mark.problem("1.1")
@pytest.mark.parametrize("customer_id", [1, 2, 17, 500, 999])
def test_problem_1_1_your_plan_returns_duckdbs_rows(customer_id):
    plan = customer_orders(ROOT, customer_id)
    got = [tuple(r.values()) for r in plan.run().to_pylist()]
    want = duckdb_rows(f"SELECT order_id, order_date, amount FROM ORDERS WHERE customer_id = {customer_id}")
    assert got == want
    assert plan.schema().names == ["order_id", "order_date", "amount"]
    plan.metrics.check()


@pytest.mark.problem("1.1")
def test_problem_1_1_your_plan_reads_only_the_columns_it_needs():
    plan = customer_orders(ROOT, 17)
    plan.run()
    scans = [m for m in plan.metrics.walk() if m.operator == "Scan"]
    assert len(scans) == 1, "one scan of the orders"
    for column in ("note", "status", "quantity"):
        assert f" {column}" not in scans[0].detail and f":{column}" not in scans[0].detail, (
            f"the scan reads {column}, which the query never uses"
        )


# Problem 1.2 -----------------------------------------------------------------------------------


@pytest.mark.problem("1.2")
@pytest.mark.parametrize("status", ["returned", "shipped", "cancelled"])
@pytest.mark.parametrize("threshold", [0, 50, 100, 200, 300])
def test_problem_1_2_the_recipe_predicts_duckdbs_count(status, threshold):
    rows = duckdb_rows("SELECT count(*) FROM ORDERS")[0][0]
    share = duckdb_rows(f"SELECT count(*) FROM ORDERS WHERE status = '{status}'")[0][0] / rows
    low, high = duckdb_rows("SELECT min(amount / quantity), max(amount / quantity) FROM ORDERS")[0]
    counted = duckdb_rows(
        f"SELECT count(*) FROM ORDERS WHERE status = '{status}' AND amount / quantity > {threshold}"
    )[0][0]
    expected = expected_rows(rows, share, low, high, threshold)
    assert abs(expected - counted) <= max(0.05 * counted, 25), (
        f"{status} over {threshold}: you expect {expected:,.0f} rows, DuckDB counts {counted:,}"
    )


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        customer_orders(ROOT, 17)
    with pytest.raises(NotImplementedError):
        expected_rows(100, 0.5, 0.0, 1.0, 0.5)


def test_the_graders_expectations_can_be_computed():
    assert duckdb_rows("SELECT count(*) FROM ORDERS WHERE customer_id = 17")[0][0] > 0
