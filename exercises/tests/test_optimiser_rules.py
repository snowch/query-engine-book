"""Graders for ch12's problems. Each expected answer is derived at test time, from DuckDB or by
evaluating the conditions on the orders. None is stored."""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from optimiser_rules import across_the_join, move_constants

from query_lab import planner, rules, sql
from query_lab.expressions import Call, Column, Literal, evaluate
from query_lab.operators import Scan
from query_lab.reference import connect

ROOT = Path(__file__).resolve().parents[2]
ORDERS = ROOT / "fixtures" / "orders-sorted.parquet"
CUSTOMERS = ROOT / "fixtures" / "customers.parquet"


def condition(text: str):
    return sql.parse(f"SELECT x FROM 't' WHERE {text}").where


def plan_with(rule, text: str) -> planner.Node:
    logical = planner.logical_plan(ROOT, sql.parse(text))
    return rules.push_filters(rule(logical))


def rows(logical: planner.Node) -> list[tuple]:
    table = planner.physical_plan(ROOT, logical).run()
    return sorted(tuple(r.values()) for r in table.to_pylist())


def in_selects(node: planner.Node, rule):
    """``node`` with ``rule`` applied to the condition of every filter in it."""
    children = [in_selects(c, rule) for c in node.children]
    if isinstance(node, planner.Select):
        return planner.Select(children=children, condition=rule(node.condition))
    node.children = children
    return node


# Problem 12.1 ----------------------------------------------------------------------------------

MOVABLE = [
    "quantity + 1 > 3",
    "2 + quantity <= 5",
    "quantity - 3 = 1",
    "7 < quantity + 2",
    "amount - 100 >= 900",
    "quantity + 1 > 3 AND amount - 1 < 50",
]


@pytest.mark.problem("12.1")
@pytest.mark.parametrize("text", MOVABLE)
def test_problem_12_1_each_condition_reaches_the_scan(text):
    query = f"SELECT order_id FROM '{ORDERS}' WHERE {text}"
    logical = rules.push_filters(in_selects(planner.logical_plan(ROOT, sql.parse(query)), move_constants))
    assert not any(isinstance(n, planner.Select) for n in logical.walk()), (
        f"WHERE {text}: part of it still needs a filter above the scan"
    )
    assert rows(logical) == sorted(connect().execute(query).fetchall())


@pytest.mark.problem("12.1")
def test_problem_12_1_rewrites_keep_every_rows_answer():
    batch = Scan(ORDERS, ["quantity", "amount", "status"]).run().to_batches()[0]
    rng = random.Random(12)
    for _ in range(200):
        column = rng.choice(["quantity", "amount"])
        a, b = rng.randint(-5, 9), rng.randint(-5, 900)
        op, arith = rng.choice(["=", "!=", "<", "<=", ">", ">="]), rng.choice(["+", "-"])
        left = (
            Call(arith, (Column(column), Literal(a)))
            if rng.random() < 0.7
            else Call("+", (Literal(a), Column(column)))
        )
        original = Call(op, (left, Literal(b)) if rng.random() < 0.5 else (Literal(b), left))
        if rng.random() < 0.3:
            original = Call("not", (original,))
        moved = move_constants(original)
        assert evaluate(moved, batch).to_pylist() == evaluate(original, batch).to_pylist(), (
            f"{original} became {moved}, which differs on some rows"
        )


@pytest.mark.problem("12.1")
@pytest.mark.parametrize(
    "text",
    ["quantity * 2 > 4", "amount / quantity > 100", "quantity + amount > 3", "lower(status) = 'shipped'"],
)
def test_problem_12_1_leaves_what_it_cannot_move(text):
    assert move_constants(condition(text)) == condition(text)


# Problem 12.2 ----------------------------------------------------------------------------------

JOINED = (
    f"SELECT o.order_id, c.country FROM '{ORDERS}' AS o "
    f"JOIN '{CUSTOMERS}' AS c ON o.customer_id = c.customer_id WHERE "
)
KEYED = [
    "c.customer_id < 40",
    "o.customer_id >= 990",
    "c.customer_id = 7 AND c.segment = 'enterprise'",
    "40 > o.customer_id AND o.amount > 1000",
]


def filtered_gets(logical: planner.Node) -> dict[str, list]:
    return {n.table.alias: [str(f) for f in n.filters] for n in logical.walk() if isinstance(n, planner.Get)}


@pytest.mark.problem("12.2")
@pytest.mark.parametrize("text", KEYED)
def test_problem_12_2_both_scans_test_the_key(text):
    logical = plan_with(across_the_join, JOINED + text)
    filters = filtered_gets(logical)
    for alias in ("o", "c"):
        assert any(f.startswith("customer_id ") for f in filters[alias]), (
            f"WHERE {text}: the {alias} scan tests no customer_id: {filters[alias]}"
        )
    assert rows(logical) == sorted(connect().execute(JOINED + text).fetchall())


@pytest.mark.problem("12.2")
def test_problem_12_2_the_orders_scan_hands_up_fewer_rows():
    text = JOINED + "c.customer_id < 40"
    plain = planner.physical_plan(ROOT, rules.push_filters(planner.logical_plan(ROOT, sql.parse(text))))
    yours = planner.physical_plan(ROOT, plan_with(across_the_join, text))
    for op in (plain, yours):
        op.run()
    scanned = [
        next(m for m in op.metrics.walk() if m.operator == "Scan" and "orders" in m.detail).rows_out
        for op in (plain, yours)
    ]
    assert scanned[1] < scanned[0]


@pytest.mark.problem("12.2")
@pytest.mark.parametrize(
    "text", ["c.segment = 'enterprise'", "o.amount > 2000 OR c.customer_id < 5", "o.quantity < 3"]
)
def test_problem_12_2_other_conditions_are_left_alone(text):
    plain = rules.push_filters(planner.logical_plan(ROOT, sql.parse(JOINED + text)))
    assert planner.show(plan_with(across_the_join, JOINED + text)) == planner.show(plain)


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        move_constants(condition("quantity + 1 > 3"))
    with pytest.raises(NotImplementedError):
        across_the_join(planner.logical_plan(ROOT, sql.parse(JOINED + "c.customer_id < 40")))


def test_the_graders_expectations_can_be_computed():
    assert connect().execute(JOINED + "c.customer_id < 40").fetchall()
