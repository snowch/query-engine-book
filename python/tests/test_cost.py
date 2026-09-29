"""Estimates from the footer, and the order of joins chosen by them (ch13)."""

from __future__ import annotations

from functools import partial
from pathlib import Path

import pytest

from query_lab import cost, planner, rules, sql
from query_lab.operators import Comparison
from query_lab.reference import connect, read_query

ROOT = Path(__file__).resolve().parents[2]
ORDERS = ROOT / "fixtures" / "orders-sorted.parquet"


def plan(text: str, chosen=(rules.push_filters,)) -> planner.Node:
    node = planner.logical_plan(ROOT, sql.parse(text))
    for rule in chosen:
        node = rule(node)
    return node


def test_the_footer_gives_rows_ranges_and_bounds_on_distinct_values():
    stats = cost.table_stats(ORDERS)
    assert stats.rows == connect().execute(f"SELECT count(*) FROM '{ORDERS}'").fetchone()[0]
    assert (
        stats.columns["customer_id"].distinct
        == stats.columns["customer_id"].high - stats.columns["customer_id"].low + 1
    )
    assert stats.columns["status"].distinct is None
    assert stats.columns["status"].bound == stats.rows


@pytest.mark.parametrize("days", [1, 31, 100, 366])
def test_a_range_on_evenly_spread_dates_is_estimated_closely(days):
    text = f"SELECT order_id FROM '{ORDERS}' WHERE order_date < DATE '2024-01-01' + INTERVAL {days} DAY"
    import datetime as dt

    last = dt.date(2024, 1, 1) + dt.timedelta(days=days)
    ours = cost.estimate(ROOT, plan(f"SELECT order_id FROM '{ORDERS}' WHERE order_date < DATE '{last}'"))
    counted = connect().execute(f"SELECT count(*) FROM ({text})").fetchone()[0]
    assert abs(ours - counted) <= 0.01 * cost.table_stats(ORDERS).rows + 60


def test_conditions_are_combined_as_if_independent():
    columns = cost.table_stats(ORDERS).columns
    a, b = Comparison("quantity", "=", 1), Comparison("amount", ">", 300.0)
    both = sql.parse("SELECT x FROM 't' WHERE quantity = 1 AND amount > 300").where
    assert cost.selectivity(both, columns) == pytest.approx(
        cost.selectivity(a, columns) * cost.selectivity(b, columns)
    )


def test_a_value_outside_the_range_is_estimated_to_keep_nothing():
    assert cost.estimate(ROOT, plan(f"SELECT order_id FROM '{ORDERS}' WHERE customer_id = 5000")) == 0


def test_the_join_order_rule_joins_the_small_tables_first_and_keeps_duckdbs_rows():
    text = read_query(ROOT / "queries" / "asian_orders.sql")
    chosen = (rules.push_filters, partial(cost.join_order, ROOT), rules.prune_columns)
    logical = plan(text, chosen)
    top = next(n for n in logical.walk() if isinstance(n, planner.Join))
    inner = top.children[1]
    assert isinstance(inner, planner.Join) and {inner.left_key, inner.right_key} == {"c.country", "n.country"}
    assert cost.joined_rows(ROOT, logical) < cost.joined_rows(ROOT, plan(text))
    ours = sorted(tuple(r.values()) for r in planner.physical_plan(ROOT, logical).run().to_pylist())
    assert ours == sorted(connect().execute(text).fetchall())


def test_each_join_builds_on_its_smaller_input():
    text = read_query(ROOT / "queries" / "customers_with_orders.sql")
    logical = plan(text, (rules.push_filters, partial(cost.join_order, ROOT)))
    join = next(n for n in logical.walk() if isinstance(n, planner.Join))
    probe, build = join.children
    assert cost.estimate(ROOT, build) <= cost.estimate(ROOT, probe)
