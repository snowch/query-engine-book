"""The optimiser's rules: the same rows as DuckDB, and the plans the book wrote by hand (ch12)."""

from __future__ import annotations

from pathlib import Path

import pytest

from query_lab import planner, plans, rules, sql
from query_lab.reference import connect, read_query

ROOT = Path(__file__).resolve().parents[2]
QUERIES = sorted(p.name for p in (ROOT / "queries").glob("*.sql"))
#: The plans written by hand that the rules cannot rebuild from the text: the page index is a way
#: of scanning a file, not a rewrite of the plan.
NOT_A_REWRITE = {"early_march_paged.sql"}


def plannable(query: str) -> bool:
    try:
        planner.logical_plan(ROOT, sql.parse(read_query(ROOT / "queries" / query)))
    except planner.PlanError:
        return False
    return True


def logical(query: str, chosen=rules.RULES) -> planner.Node:
    node = planner.logical_plan(ROOT, sql.parse(read_query(ROOT / "queries" / query)))
    for rule in chosen:
        node = rule(node)
    return node


def rounded(rows):
    return [tuple(round(v, 6) if isinstance(v, float) else v for v in r) for r in rows]


@pytest.mark.parametrize("query", [q for q in QUERIES if plannable(q)])
def test_the_rules_keep_duckdbs_rows(query):
    text = read_query(ROOT / "queries" / query)
    ours = rounded(tuple(r.values()) for r in planner.plan(ROOT, text, rules.RULES).run().to_pylist())
    theirs = rounded(connect().execute(text).fetchall())
    if "order by" not in text.lower():
        ours, theirs = sorted(ours, key=repr), sorted(theirs, key=repr)
    assert ours == theirs


@pytest.mark.parametrize("query", sorted(q for q in set(plans.PLANS) - NOT_A_REWRITE if plannable(q)))
def test_the_rules_read_what_the_hand_written_plan_reads(query):
    ours = planner.plan(ROOT, read_query(ROOT / "queries" / query), rules.RULES)
    written = plans.plan_for(ROOT, query)
    for op in (ours, written):
        op.run()
    assert sum(m.bytes_read for m in ours.metrics.walk()) == sum(m.bytes_read for m in written.metrics.walk())


def test_each_condition_goes_to_its_own_table():
    gets = {n.table.alias: n for n in logical("enterprise_orders.sql").walk() if isinstance(n, planner.Get)}
    assert [str(f) for f in gets["c"].filters] == ["segment = enterprise"]
    assert gets["c"].columns == ["customer_id", "country"]
    # The price is an expression: it cannot go into the scan, so it is tested just above it.
    above = next(n for n in logical("enterprise_orders.sql").walk() if isinstance(n, planner.Select))
    assert above.children[0] is gets["o"] or above.children[0] == gets["o"]


def test_a_condition_that_reads_both_tables_stays_above_the_join():
    steps = [type(n).__name__ for n in logical("enterprise_or_large.sql").walk()]
    assert steps == ["Compute", "Select", "Join", "Get", "Get"]


def test_a_count_of_rows_reads_one_column():
    node = rules.prune_columns(
        planner.logical_plan(ROOT, sql.parse("SELECT count(*) FROM 'fixtures/customers.parquet'"))
    )
    get = next(n for n in node.walk() if isinstance(n, planner.Get))
    assert len(get.columns) == 1


def test_a_sort_under_a_limit_becomes_a_top_k_and_a_sort_alone_does_not():
    assert any(isinstance(n, planner.Top) for n in logical("top_orders.sql").walk())
    assert not any(isinstance(n, planner.Top) for n in logical("orders_by_amount.sql").walk())
    assert (
        planner.plan(ROOT, read_query(ROOT / "queries" / "top_orders.sql"), rules.RULES).metrics.operator
        == "TopK"
    )
