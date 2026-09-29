"""Graders for ch15's problems. Each expected answer is derived at test time, by running the
book's simulated nodes. None is stored."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest
from partitioning_and_shuffle import already_placed, choose_join

from query_lab import distributed as d

ROOT = Path(__file__).resolve().parents[2]
ORDERS = ROOT / "fixtures" / "orders-sorted.parquet"
CUSTOMERS = ROOT / "fixtures" / "customers.parquet"


# Problem 15.1 ----------------------------------------------------------------------------------


@pytest.mark.problem("15.1")
@pytest.mark.parametrize("nodes", [1, 2, 4, 7])
def test_problem_15_1_placement_is_whether_a_shuffle_sends_nothing(nodes):
    placed = d.place(ORDERS, ["order_id", "customer_id"], nodes)
    shuffled, _ = d.shuffle(placed, "customer_id")
    for parts in (placed, shuffled):
        again, sent = d.shuffle(parts, "customer_id")
        assert already_placed(parts, "customer_id") == (sent == 0)
    assert already_placed(shuffled, "customer_id")
    assert already_placed(d.shuffle(placed, "order_id")[0], "order_id")


@pytest.mark.problem("15.1")
def test_problem_15_1_one_row_out_of_place_is_enough():
    parts, _ = d.shuffle(d.place(ORDERS, ["order_id", "customer_id"], 4), "customer_id")
    stray = parts[0].slice(0, 1)
    moved = [parts[0].slice(1), pa.concat_tables([parts[1], stray]), parts[2], parts[3]]
    assert not already_placed(moved, "customer_id")


# Problem 15.2 ----------------------------------------------------------------------------------


@pytest.mark.problem("15.2")
@pytest.mark.parametrize("nodes", [2, 4, 8, 16, 32, 64])
@pytest.mark.parametrize("segment", [None, "enterprise"])
def test_problem_15_2_your_choice_sends_no_more_than_the_other(nodes, segment):
    orders = [
        t.select(["order_id", "customer_id"]) for t in d.place(ORDERS, ["order_id", "customer_id"], nodes)
    ]
    customers = pq.read_table(CUSTOMERS, columns=["customer_id", "country", "segment"])
    if segment:
        customers = customers.filter(pc.equal(customers["segment"], segment))
    customers = customers.select(["customer_id", "country"])
    held = [customers] + [customers.slice(0, 0)] * (nodes - 1)
    sent = {
        "broadcast": d.join_by_broadcast(orders, customers).shuffled,
        "shuffle": d.join_by_shuffle(orders, held).shuffled,
    }
    probe = sum(d.ipc_bytes(t) for t in orders)
    chosen = choose_join(probe, d.ipc_bytes(customers), nodes)
    assert chosen in sent
    other = "shuffle" if chosen == "broadcast" else "broadcast"
    # Near where the two cross, an estimate from sizes alone may pick either: a quarter is allowed.
    assert sent[chosen] <= sent[other] * 1.25, (
        f"{nodes} nodes: {chosen} sends {sent[chosen]:,} bytes, {other} {sent[other]:,}"
    )


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    parts = d.place(ORDERS, ["customer_id"], 2)
    with pytest.raises(NotImplementedError):
        already_placed(parts, "customer_id")
    with pytest.raises(NotImplementedError):
        choose_join(100, 10, 4)


def test_the_graders_expectations_can_be_computed():
    assert d.shuffle(d.place(ORDERS, ["customer_id"], 2), "customer_id")[1] > 0
