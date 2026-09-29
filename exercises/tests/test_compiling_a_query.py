"""Graders for ch19's problems. Each expected answer is derived at test time: from DuckDB, or from
the trees the grader built. None is stored."""

from __future__ import annotations

import ast
import random
from pathlib import Path

import pytest
from compiling_a_query import Parameter, generate_totals, parameterise

from query_lab.compile import Pipeline, divide
from query_lab.expressions import Call, Column, Literal, nodes
from query_lab.operators import Scan
from query_lab.reference import connect
from query_lab.sql import parse

ROOT = Path(__file__).resolve().parents[2]
ORDERS = ROOT / "fixtures" / "orders-sorted.parquet"

# Problem 19.1 ----------------------------------------------------------------------------------

#: Each case: the WHERE and the summed value, in SQL, and the key.
TOTALS = [
    ("status = 'returned'", "amount", "customer_id"),
    ("status = 'returned' AND amount / quantity > 100", "amount / quantity", "customer_id"),
    ("quantity > 2 AND lower(status) != 'shipped'", "amount * 2 - quantity", "status"),
    ("amount > 1000 OR quantity = 1", "1", "quantity"),
]


@pytest.mark.problem("19.1")
@pytest.mark.parametrize("where, value, key", TOTALS)
def test_problem_19_1_the_compiled_totals_are_duckdbs(where, value, key):
    pipeline = Pipeline.of(f"SELECT {value} AS v FROM 't' WHERE {where}")
    source = generate_totals(list(pipeline.filters), key, pipeline.outputs[0][1])
    tree = ast.parse(source)
    assert sum(isinstance(n, (ast.For, ast.While)) for n in ast.walk(tree)) == 1, (
        "write one loop over the rows"
    )
    assert "compute" not in source and "pc." not in source, "call no kernel: compute each value in the loop"
    scope = {"divide": divide}
    exec(compile(source, "<totals>", "exec"), scope)
    columns = sorted({*pipeline.columns(), key})
    sums: dict = {}
    for batch in Scan(ORDERS, columns).batches():
        scope["totals"](batch, sums)
    theirs = (
        connect()
        .execute(f"SELECT {key}, sum({value}) FROM '{ORDERS}' WHERE {where} GROUP BY {key}")
        .fetchall()
    )
    assert sorted(sums) == sorted(k for k, _ in theirs)
    for k, total in theirs:
        assert sums[k] == pytest.approx(total), f"{key} = {k}"


# Problem 19.2 ----------------------------------------------------------------------------------


def bind(shape, constants):
    """The tree again, each parameter replaced by its constant."""
    match shape:
        case Parameter(index):
            return Literal(constants[index])
        case Call(op, args):
            return Call(op, tuple(bind(a, constants) for a in args))
    return shape


def random_tree(rng: random.Random, depth: int = 0):
    if depth > 3 or rng.random() < 0.3:
        return rng.choice([Column("amount"), Column("quantity"), Literal(rng.randint(0, 9)), Literal("x")])
    return Call(
        rng.choice(["+", "*", ">", "=", "and"]), (random_tree(rng, depth + 1), random_tree(rng, depth + 1))
    )


@pytest.mark.problem("19.2")
def test_problem_19_2_the_shape_and_constants_give_back_the_tree():
    rng = random.Random(19)
    for _ in range(300):
        tree = random_tree(rng)
        shape, constants = parameterise(tree)
        assert not any(isinstance(n, Literal) for n in nodes(shape)), "a constant is left in the shape"
        assert bind(shape, constants) == tree
        literals = [n.value for n in nodes(tree) if isinstance(n, Literal)]
        assert list(constants) == literals, "number the constants in the order a walk meets them"


@pytest.mark.problem("19.2")
def test_problem_19_2_queries_that_differ_only_in_constants_share_a_shape():
    def where(text):
        return parse(f"SELECT 1 AS one FROM 't' WHERE {text}").where

    a = parameterise(where("status = 'returned' AND amount / quantity > 100"))
    b = parameterise(where("status = 'shipped' AND amount / quantity > 250.5"))
    c = parameterise(where("status = 'returned' AND amount * quantity > 100"))
    assert a[0] == b[0] and a[1] != b[1]
    assert a[0] != c[0], "a different operator is a different shape"
    assert a[1] == ("returned", 100)
