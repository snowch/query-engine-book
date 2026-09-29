"""The hash join, against DuckDB, and what its build side costs (ch08)."""

from __future__ import annotations

from pathlib import Path

import pytest

from query_lab import plans, report
from query_lab.aggregate import HashTable
from query_lab.cache import Cache
from query_lab.join import ROW_BYTES, HashJoin
from query_lab.operators import Comparison, Scan
from query_lab.reference import connect

ROOT = Path(__file__).resolve().parents[2]
ORDERS = ROOT / "fixtures" / "orders-sorted.parquet"
CUSTOMERS = ROOT / "fixtures" / "customers.parquet"


def duckdb(sql: str) -> list[tuple]:
    return sorted(connect().execute(sql).fetchall())


@pytest.mark.parametrize("build_on_customers", [True, False])
def test_either_build_side_joins_duckdbs_rows(build_on_customers):
    plan = plans.orders_with_country(ROOT) if build_on_customers else plans.customers_with_orders(ROOT)
    ours = sorted(tuple(r.values()) for r in plan.run().to_pylist())
    theirs = duckdb(
        f"SELECT o.order_id, c.country FROM '{ORDERS}' o JOIN '{CUSTOMERS}' c ON o.customer_id = c.customer_id"
    )
    assert ours == theirs
    plan.metrics.check()


def test_a_filtered_build_side_joins_only_its_rows_and_holds_only_them():
    customers = Scan(
        CUSTOMERS, ["customer_id", "segment"], filters=[Comparison("segment", "=", "enterprise")]
    )
    orders = Scan(ORDERS, ["order_id", "customer_id"])
    join = HashJoin(
        orders, customers, "customer_id", "customer_id", [("probe", "order_id"), ("build", "segment")]
    )
    ours = sorted(tuple(r.values()) for r in join.run().to_pylist())
    theirs = duckdb(
        f"SELECT o.order_id, c.segment FROM '{ORDERS}' o JOIN '{CUSTOMERS}' c ON o.customer_id = c.customer_id "
        "WHERE c.segment = 'enterprise'"
    )
    assert ours == theirs
    assert (
        join.build_rows
        == connect().execute(f"SELECT count(*) FROM '{CUSTOMERS}' WHERE segment = 'enterprise'").fetchone()[0]
    )


def test_a_many_to_many_join_hands_up_every_pair():
    some = [Comparison("customer_id", ">=", 100), Comparison("customer_id", "<=", 120)]
    small = Scan(ORDERS, ["order_id", "customer_id"], filters=some)
    again = Scan(ORDERS, ["order_id", "customer_id"], filters=some)
    join = HashJoin(
        small, again, "customer_id", "customer_id", [("probe", "order_id"), ("build", "order_id")]
    )
    table = join.run()
    ours = sorted(zip(*(column.to_pylist() for column in table.columns), strict=True))
    assert ours == duckdb(
        f"SELECT a.order_id, b.order_id FROM '{ORDERS}' a JOIN '{ORDERS}' b ON a.customer_id = b.customer_id "
        "WHERE a.customer_id BETWEEN 100 AND 120"
    )


def test_the_join_holds_its_build_rows_and_its_table():
    plan = plans.orders_with_country(ROOT)
    plan.run()
    assert plan.build_rows == plan.build.metrics.rows_out
    assert plan.held_bytes == plan.build_rows * ROW_BYTES * 2 + plan.table.table_bytes
    assert plan.metrics.rows_in == plan.probe.metrics.rows_out + plan.build.metrics.rows_out


def test_building_on_the_small_side_holds_less_and_misses_less():
    small, large = plans.orders_with_country(ROOT), plans.customers_with_orders(ROOT)
    for plan in (small, large):
        plan.table = HashTable(cache=Cache())
        plan.run()
    assert small.held_bytes < large.held_bytes
    assert small.table.cache.misses < large.table.cache.misses


def test_a_lookup_that_finds_nothing_inserts_nothing():
    table = HashTable()
    table.find("a")
    assert table.get("b") is None and table.get("a") == 0
    assert table.keys == ["a"]


def test_the_joins_report_is_the_engines():
    data = report.run(ROOT, {"experiment": "measure", "of": "joins"})
    small, large, filtered = data["cases"]
    assert small["reference"]["value"] == large["reference"]["value"]
    assert small["measured"] < large["measured"] and filtered["measured"] < small["measured"]
    points = data["chart"]["series"][0]["points"]
    assert [y for _, y in points] == sorted(y for _, y in points), "misses grow with the build side"
