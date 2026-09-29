"""Skewed keys on simulated nodes, and salting them (ch16)."""

from __future__ import annotations

from pathlib import Path

import pytest

from query_lab import distributed as d
from query_lab import skew
from query_lab.reference import connect, read_query

ROOT = Path(__file__).resolve().parents[2]


def spread(nodes: int):
    orders = d.place(ROOT / "fixtures" / "orders-sorted.parquet", ["order_id", "customer_id"], nodes)
    return orders, d.place(ROOT / "fixtures" / "customers.parquet", ["customer_id", "country"], nodes)


def test_the_heaviest_customer_is_heavy():
    orders, _ = spread(16)
    assert 1 in skew.heavy_keys(orders, "customer_id", 16)


@pytest.mark.parametrize("nodes", [2, 8, 16])
def test_a_salted_join_gives_duckdbs_rows(nodes):
    result = skew.join_salted(*spread(nodes), nodes)
    theirs = sorted(connect().execute(read_query(ROOT / "queries" / "orders_with_country.sql")).fetchall())
    assert sorted(tuple(r.values()) for r in result.table().to_pylist()) == theirs


def test_salting_lightens_the_busiest_node_on_many_nodes():
    orders, customers = spread(16)
    assert (
        skew.busiest(skew.join_salted(orders, customers, 16).parts)
        < skew.busiest(d.join_by_shuffle(orders, customers).parts) / 1.5
    )


def test_a_heavy_keys_other_side_is_copied_to_every_node_it_is_spread_over():
    where = skew.copied("customer_id", {1}, 4, 16)
    orders, customers = spread(16)
    first = customers[0].slice(0, 1)
    assert len(where(first)[0]) == (4 if first.column("customer_id")[0].as_py() == 1 else 1)
