"""Graders for ch11's problems. Each expected answer is derived at test time, from DuckDB. None is
stored."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from from_sql_to_a_logical_plan import Parser, resolve_ordinals

from query_lab import planner, sql
from query_lab.expressions import Call, Literal
from query_lab.reference import connect

ROOT = Path(__file__).resolve().parents[2]
ORDERS = f"'{ROOT / 'fixtures' / 'orders-sorted.parquet'}'"


def engine(query: sql.Query) -> list[tuple]:
    table = planner.physical_plan(ROOT, planner.logical_plan(ROOT, query)).run()
    return [tuple(r.values()) for r in table.to_pylist()]


def duckdb(text: str) -> list[tuple]:
    return connect().execute(text).fetchall()


def rounded(rows: list[tuple]) -> list[tuple]:
    return [tuple(round(v, 6) if isinstance(v, float) else v for v in r) for r in rows]


# Problem 11.1 ----------------------------------------------------------------------------------

CONDITIONS = [
    "amount BETWEEN 100 AND 200",
    "quantity NOT BETWEEN 2 AND 8",
    "status IN ('returned', 'cancelled')",
    "customer_id NOT IN (1, 2, 3, 5, 8)",
    "quantity IN (3)",
    "amount BETWEEN 10 * 10 AND 150 + 50 AND status = 'shipped'",
    "status = 'returned' OR quantity BETWEEN 9 AND 10",
    "NOT quantity IN (1, 2) AND amount / quantity BETWEEN 20 AND 30",
]


@pytest.mark.problem("11.1")
@pytest.mark.parametrize("condition", CONDITIONS)
def test_problem_11_1_your_parser_keeps_duckdbs_rows(condition):
    text = f"SELECT order_id FROM {ORDERS} WHERE {condition}"
    got = engine(Parser(text).query())
    assert sorted(got) == sorted(duckdb(text)), f"WHERE {condition}: your rows differ from DuckDB's"


@pytest.mark.problem("11.1")
def test_problem_11_1_the_tree_uses_only_the_engines_calls():
    text = f"SELECT order_id FROM {ORDERS} WHERE quantity NOT BETWEEN 2 AND 8 OR status IN ('a', 'b')"
    ops = set()

    def walk(e):
        if isinstance(e, Call):
            ops.add(e.op)
            for a in e.args:
                walk(a)

    walk(Parser(text).query().where)
    assert ops <= {">=", "<=", "=", "and", "or", "not"}, f"calls the engine cannot evaluate: {ops}"


@pytest.mark.problem("11.1")
def test_problem_11_1_the_other_comparisons_still_read():
    for text in (f"SELECT order_id FROM {ORDERS} WHERE amount > 2400", "SELECT 1 + 2 * 3 AS x FROM 't'"):
        assert Parser(text).query() == sql.parse(text)


@pytest.mark.problem("11.1")
@pytest.mark.parametrize(
    "broken", ["amount BETWEEN 1", "amount BETWEEN 1 OR 2", "status IN 'a'", "status IN ()"]
)
def test_problem_11_1_broken_conditions_are_errors(broken):
    with pytest.raises(sql.SQLError):
        Parser(f"SELECT order_id FROM {ORDERS} WHERE {broken}").query()


# Problem 11.2 ----------------------------------------------------------------------------------

ORDINALS = [
    f"SELECT order_id, amount FROM {ORDERS} ORDER BY 2 DESC, 1 LIMIT 20",
    f"SELECT status, count(*) AS orders FROM {ORDERS} GROUP BY 1 ORDER BY 2 DESC",
    f"SELECT quantity, status, sum(amount) FROM {ORDERS} GROUP BY 1, 2 ORDER BY 1, 2",
    f"SELECT customer_id, amount / quantity AS unit_price FROM {ORDERS} ORDER BY 2 DESC, 1 LIMIT 5",
    f"SELECT status, max(amount) FROM {ORDERS} GROUP BY status ORDER BY 2",
]


@pytest.mark.problem("11.2")
@pytest.mark.parametrize("text", ORDINALS)
def test_problem_11_2_ordinals_give_duckdbs_rows(text):
    got = engine(resolve_ordinals(sql.parse(text)))
    assert rounded(got) == rounded(duckdb(text)), f"{text}: your rows differ from DuckDB's"


@pytest.mark.problem("11.2")
def test_problem_11_2_group_by_takes_the_items_expression():
    query = resolve_ordinals(sql.parse(f"SELECT amount / quantity AS p, count(*) FROM {ORDERS} GROUP BY 1"))
    assert query.group_by == [sql.parse(f"SELECT amount / quantity FROM {ORDERS}").items[0].expr]


@pytest.mark.problem("11.2")
def test_problem_11_2_the_query_you_were_given_is_unchanged():
    query = sql.parse(f"SELECT status, count(*) FROM {ORDERS} GROUP BY 1 ORDER BY 2 DESC")
    before = copy.deepcopy(query)
    resolve_ordinals(query)
    assert query == before


@pytest.mark.problem("11.2")
@pytest.mark.parametrize("n", [0, 3])
def test_problem_11_2_a_number_no_item_has_is_an_error(n):
    with pytest.raises(ValueError):
        resolve_ordinals(sql.parse(f"SELECT status, count(*) FROM {ORDERS} GROUP BY 1 ORDER BY {n}"))


@pytest.mark.problem("11.2")
def test_problem_11_2_other_keys_are_kept():
    text = f"SELECT status, count(*) AS n FROM {ORDERS} GROUP BY status ORDER BY n DESC"
    assert resolve_ordinals(sql.parse(text)) == sql.parse(text)


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        Parser(f"SELECT order_id FROM {ORDERS} WHERE amount > 1").query()
    with pytest.raises(NotImplementedError):
        resolve_ordinals(sql.parse(f"SELECT order_id FROM {ORDERS} ORDER BY 1"))


def test_the_graders_expectations_can_be_computed():
    assert duckdb(f"SELECT order_id FROM {ORDERS} WHERE amount BETWEEN 1 AND 2 LIMIT 1") is not None
    assert isinstance(sql.parse(f"SELECT order_id FROM {ORDERS} ORDER BY 1").order_by[0][0], Literal)
