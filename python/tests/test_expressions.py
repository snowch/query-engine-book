"""Expressions evaluated a row and a batch at a time, and the processor model (ch06)."""

from __future__ import annotations

import random
from pathlib import Path

import pyarrow.compute as pc
import pytest

from query_lab import plans, report
from query_lab.cpu import LANES, Predictor, VectorUnit, select_with_branch, select_without_branch
from query_lab.expressions import Call, Column, Counts, Literal, batches_of, evaluate, evaluate_row, nodes
from query_lab.operators import Scan

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def orders():
    return Scan(ROOT / "fixtures" / "orders-sorted.parquet", ["order_id", "amount", "quantity"]).run()


def tree(rng: random.Random, depth: int):
    if depth == 0 or rng.random() < 0.3:
        return rng.choice([Column("amount"), Column("quantity"), Literal(rng.randint(1, 9)), Literal(0.5)])
    return Call(rng.choice("+-*/"), (tree(rng, depth - 1), tree(rng, depth - 1)))


def test_a_row_at_a_time_and_a_batch_at_a_time_compute_the_same_values(orders):
    rng = random.Random(6)
    rows = orders.to_pylist()[:500]
    batch = orders.slice(0, 500).combine_chunks().to_batches()[0]
    for expr in [plans.WITH_TAX, plans.WITH_TAX_WHERE] + [tree(rng, 4) for _ in range(40)]:
        whole = evaluate(expr, batch)
        whole = whole.to_pylist() if hasattr(whole, "to_pylist") else [whole.as_py()] * len(rows)
        assert whole == [evaluate_row(expr, r) for r in rows], str(expr)


def test_a_row_at_a_time_visits_every_node_for_every_row_and_a_batch_once_per_batch(orders):
    where = plans.WITH_TAX_WHERE
    size = len(list(nodes(where)))
    by_row = Counts()
    for r in orders.to_pylist():
        evaluate_row(where, r, by_row)
    assert by_row.dispatches == size * orders.num_rows
    by_batch = Counts()
    batches = list(batches_of(orders, 2048))
    for b in batches:
        evaluate(where, b, by_batch)
    assert by_batch.dispatches == size * len(batches)


def test_the_vector_unit_fills_its_lanes_but_for_the_last_instruction():
    unit = VectorUnit()
    unit.run(LANES * 10 + 1)
    assert unit.instructions == 11 and unit.values == LANES * 10 + 1
    one = VectorUnit()
    for _ in range(8):
        one.run(1)
    assert one.instructions == 8, "a value at a time takes an instruction each, however wide the register"


def test_the_predictor_learns_a_run_and_is_wrong_about_an_alternation():
    run = Predictor()
    for _ in range(100):
        run.branch("b", True)
    assert run.mispredictions == 1, "starting at 1, only the first taken branch surprises it"
    flip = Predictor()
    for i in range(100):
        flip.branch("b", i % 2 == 0)
    assert flip.mispredictions == 100


def test_both_kernels_select_the_rows_arrow_does_and_only_one_branches_on_the_data(orders):
    amounts = orders.column("amount").to_pylist()
    want = pc.indices_nonzero(pc.greater(orders.column("amount"), 500.0)).to_pylist()
    with_branch, without = Predictor(), Predictor()
    assert select_with_branch(amounts, lambda v: v > 500.0, with_branch) == want
    assert select_without_branch(amounts, lambda v: v > 500.0, without) == want
    assert with_branch.branches == 2 * len(amounts) and without.branches == len(amounts)
    assert without.mispredictions <= 2, "only the loop's branch, wrong at its first and last"
    assert with_branch.mispredictions > len(amounts) // 4, "a test at random is guessed badly"


def test_the_branches_report_keeps_the_same_rows_both_ways():
    data = report.run(ROOT, {"experiment": "branches", "column": "amount"})
    run, random_, no_branch = data["cases"]
    assert random_["kept"] == no_branch["kept"]
    assert run["mispredictions"] < no_branch["mispredictions"] + 10 < random_["mispredictions"]
    assert [p["kept"] for p in data["sweep"]] == sorted((p["kept"] for p in data["sweep"]), reverse=True)
    assert max(data["sweep"], key=lambda p: p["with"])["kept"] in range(
        data["rows"] // 4, 3 * data["rows"] // 4
    )
    assert all(p["without"] <= 2 for p in data["sweep"])
