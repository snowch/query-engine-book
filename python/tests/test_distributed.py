"""Partitions, shuffles and broadcasts on simulated nodes: DuckDB's rows, and the bytes sent (ch15)."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pytest

from query_lab import distributed as d
from query_lab.reference import connect, read_query

ROOT = Path(__file__).resolve().parents[2]
ORDERS = ROOT / "fixtures" / "orders-sorted.parquet"
CUSTOMERS = ROOT / "fixtures" / "customers.parquet"


def spread(nodes: int):
    return d.place(ORDERS, ["order_id", "customer_id", "amount"], nodes)


def rows(table) -> list[tuple]:
    return sorted(tuple(r.values()) for r in table.to_pylist())


@pytest.mark.parametrize("nodes", [1, 3, 4, 16])
def test_a_shuffle_puts_every_row_on_its_keys_node_and_loses_none(nodes):
    parts, sent = d.shuffle(spread(nodes), "customer_id")
    assert sum(p.num_rows for p in parts) == pq.ParquetFile(ORDERS).metadata.num_rows
    for node, part in enumerate(parts):
        assert all(d.node_of(k, nodes) == node for k in part.column("customer_id").to_pylist())
    assert (sent == 0) == (nodes == 1)


@pytest.mark.parametrize("two_phases", [False, True])
def test_both_aggregates_give_duckdbs_rows(two_phases):
    result = (d.aggregate_in_two_phases if two_phases else d.aggregate_after_shuffle)(spread(4))
    theirs = connect().execute(read_query(ROOT / "queries" / "orders_per_customer.sql")).fetchall()
    ours = rows(result.table())
    assert [r[:2] for r in ours] == sorted(r[:2] for r in theirs)
    assert all(abs(a[2] - b[2]) < 1e-6 for a, b in zip(ours, sorted(theirs), strict=True))


def test_both_joins_give_duckdbs_rows():
    orders = [t.select(["order_id", "customer_id"]) for t in spread(4)]
    customers = pq.read_table(CUSTOMERS, columns=["customer_id", "country"])
    theirs = sorted(connect().execute(read_query(ROOT / "queries" / "orders_with_country.sql")).fetchall())
    shuffled = d.join_by_shuffle(orders, d.place(CUSTOMERS, ["customer_id", "country"], 4))
    assert rows(shuffled.table()) == theirs
    assert rows(d.join_by_broadcast(orders, customers).table()) == theirs


def test_two_phases_send_less_for_few_groups_and_more_for_unique_keys():
    orders = spread(4)
    assert d.aggregate_in_two_phases(orders).shuffled < d.aggregate_after_shuffle(orders).shuffled / 4
    assert (
        d.aggregate_in_two_phases(orders, "order_id").shuffled
        > d.aggregate_after_shuffle(orders, "order_id").shuffled
    )


def test_a_broadcast_sends_one_copy_to_every_other_node():
    customers = pq.read_table(CUSTOMERS, columns=["customer_id", "country"])
    assert d.broadcast(customers, 5)[1] == 4 * d.ipc_bytes(customers)
