"""Graders for ch06's problems. Each expected answer is derived at test time: by evaluating both
trees over the orders with the book's evaluator, or by running the book's branch predictor. None
is stored."""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from expressions_and_vectorised_kernels import always_wrong, fold

from query_lab.cpu import Predictor
from query_lab.expressions import Call, Column, Literal, evaluate, nodes
from query_lab.operators import Scan
from query_lab.plans import WITH_TAX, WITH_TAX_WHERE

ROOT = Path(__file__).resolve().parents[2]
NUMBERS = ("amount", "quantity", "order_id")


@pytest.fixture(scope="module")
def orders():
    columns = ["order_id", "amount", "quantity"]
    return Scan(ROOT / "fixtures" / "orders-sorted.parquet", columns).run().combine_chunks().to_batches()[0]


def number(rng: random.Random, depth: int, constant: bool = False):
    """A random numeric expression; ``constant`` makes one that depends on no column."""
    if depth == 0 or rng.random() < 0.25:
        if constant or rng.random() < 0.5:
            return Literal(rng.choice([rng.randint(1, 9), rng.choice([0.5, 1.25, 2.0, 10.0])]))
        return Column(rng.choice(NUMBERS))
    whole = constant or rng.random() < 0.3
    op = rng.choice("+-*/")
    return Call(op, (number(rng, depth - 1, whole), number(rng, depth - 1, whole)))


def condition(rng: random.Random, depth: int):
    """A random condition: comparisons of numeric expressions, joined by ``and`` and ``or``."""
    if depth == 0 or rng.random() < 0.5:
        return Call(rng.choice(["<", "<=", ">", ">=", "=", "!="]), (number(rng, 3), number(rng, 3)))
    return Call(rng.choice(["and", "or"]), (condition(rng, depth - 1), condition(rng, depth - 1)))


def constant_parts(expr) -> list:
    """The calls in the tree that depend on no column: every one of them should be folded."""
    return [
        n for n in nodes(expr) if isinstance(n, Call) and not any(isinstance(m, Column) for m in nodes(n))
    ]


def trees() -> list:
    rng = random.Random(6)
    out = [WITH_TAX, WITH_TAX_WHERE]
    out += [t for t in (number(rng, 4) for _ in range(90)) if isinstance(t, Call)][:60]
    out += [condition(rng, 2) for _ in range(60)]
    return out


# Problem 6.1 -----------------------------------------------------------------------------------


@pytest.mark.problem("6.1")
def test_problem_6_1_a_folded_tree_computes_what_the_tree_did(orders):
    for tree in trees():
        want = evaluate(tree, orders)
        got = evaluate(fold(tree), orders)
        if not hasattr(want, "to_pylist"):
            want = [want.as_py()] * orders.num_rows
        if not hasattr(got, "to_pylist"):
            got = [got.as_py()] * orders.num_rows
        want = want if isinstance(want, list) else want.to_pylist()
        got = got if isinstance(got, list) else got.to_pylist()
        assert got == want, f"{tree} folded to {fold(tree)}, which computes something else"


@pytest.mark.problem("6.1")
def test_problem_6_1_no_part_that_depends_on_no_column_is_left(orders):
    for tree in trees():
        folded = fold(tree)
        left = constant_parts(folded)
        assert not left, f"{tree} folded to {folded}, which still computes {left[0]} for every batch"
        kept = [n for n in nodes(tree) if isinstance(n, Column)]
        assert [n for n in nodes(folded) if isinstance(n, Column)] == kept, (
            f"{tree} folded to {folded}: a part that depends on a column must stay"
        )


# Problem 6.2 -----------------------------------------------------------------------------------


@pytest.mark.problem("6.2")
def test_problem_6_2_the_predictor_is_wrong_every_time():
    for start in range(4):
        for n in range(1, 65):
            outcomes = always_wrong(n, start)
            assert len(outcomes) == n, f"always_wrong({n}, {start}) gave {len(outcomes)} outcomes"
            predictor = Predictor()
            predictor.state["the branch"] = start
            for taken in outcomes:
                predictor.branch("the branch", bool(taken))
            right = n - predictor.mispredictions
            assert right == 0, (
                f"from {start}, the predictor was right {right} of {n} times: {outcomes[:12]}..."
            )


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        fold(WITH_TAX)
    with pytest.raises(NotImplementedError):
        always_wrong(4, 1)


def test_the_graders_expectations_can_be_computed(orders):
    assert constant_parts(WITH_TAX), "the query's own tree has a part to fold"
    assert all(isinstance(t, Call) for t in trees())
    assert evaluate(WITH_TAX_WHERE, orders).to_pylist().count(True) > 0
