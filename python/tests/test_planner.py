"""The parser and the plain planner: every query in the book they read, against DuckDB (ch11)."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pytest

from query_lab import planner, sql
from query_lab.expressions import Call, Column, Literal
from query_lab.reference import connect, read_query

ROOT = Path(__file__).resolve().parents[2]
QUERIES = sorted(p.name for p in (ROOT / "queries").glob("*.sql"))
#: The queries that read a glob of files, or pass read_parquet options: the plain planner reads
#: one plain file, and says so.
UNPLANNED = {"early_march_partition.sql", "early_march_table.sql", "orders_by_date.sql"}
ORDERS = f"'{ROOT / 'fixtures' / 'orders-sorted.parquet'}'"


def duckdb(text: str) -> list[tuple]:
    return connect().execute(text).fetchall()


def engine(text: str) -> list[tuple]:
    return [tuple(r.values()) for r in planner.plan(ROOT, text).run().to_pylist()]


def same_rows(ours: list[tuple], theirs: list[tuple], ordered: bool) -> bool:
    def rounded(rows):
        return [tuple(round(v, 6) if isinstance(v, float) else v for v in r) for r in rows]

    a, b = rounded(ours), rounded(theirs)
    return a == b if ordered else sorted(a, key=repr) == sorted(b, key=repr)


def where(text: str):
    return sql.parse(f"SELECT x FROM 't' WHERE {text}").where


@pytest.mark.parametrize("query", QUERIES)
def test_every_query_in_the_book_parses(query):
    parsed = sql.parse(read_query(ROOT / "queries" / query))
    assert parsed.star or parsed.items


def test_precedence_and_binds_tighter_than_or():
    a, b, c = (Call("=", (Column(n), Literal(1))) for n in "abc")
    assert where("a = 1 OR b = 1 AND c = 1") == Call("or", (a, Call("and", (b, c))))
    assert where("(a = 1 OR b = 1) AND c = 1") == Call("and", (Call("or", (a, b)), c))
    assert where("NOT a = 1 AND b = 1") == Call("and", (Call("not", (a,)), b))


def test_precedence_products_before_sums_and_sums_before_comparisons():
    assert where("x + 2 * 3 > 1") == Call(
        ">", (Call("+", (Column("x"), Call("*", (Literal(2), Literal(3))))), Literal(1))
    )
    # Operators of one level group from the left: a - b - c is (a - b) - c.
    assert where("x - 2 - 3 = 0").args[0] == Call("-", (Call("-", (Column("x"), Literal(2))), Literal(3)))


@pytest.mark.parametrize(
    "text, message",
    [
        ("SELECT FROM 't'", "expected a value, a column or '(', found 'FROM' at character 7"),
        ("SELECT x FROM 't' WHERE", "found the end of the query"),
        ("SELECT x FROM 't' LIMIT ten", "expected a whole number after LIMIT"),
        ("SELECT x FROM 't' WHERE a = 'open", "cannot read the text at character 28"),
    ],
)
def test_the_parser_says_what_it_expected_and_where(text, message):
    with pytest.raises(sql.SQLError, match=message.replace("(", r"\(")):
        sql.parse(text)


@pytest.mark.parametrize("query", sorted(set(QUERIES) - UNPLANNED))
def test_the_plain_plan_gives_duckdbs_rows(query):
    text = read_query(ROOT / "queries" / query)
    ordered = "order by" in text.lower()
    assert same_rows(engine(text), duckdb(text), ordered)


@pytest.mark.parametrize("query", sorted(UNPLANNED))
def test_the_plain_planner_says_what_it_cannot_read(query):
    with pytest.raises(planner.PlanError, match="one plain Parquet file"):
        planner.plan(ROOT, read_query(ROOT / "queries" / query))


def test_the_plain_plan_reads_every_column_and_filters_above_the_scan():
    text = read_query(ROOT / "queries" / "enterprise_orders.sql")
    logical = planner.logical_plan(ROOT, sql.parse(text))
    gets = [n for n in logical.walk() if isinstance(n, planner.Get)]
    for get in gets:
        assert get.columns == pq.read_schema(ROOT / get.table.path).names
        assert not get.filters
    assert [type(n).__name__ for n in logical.walk()] == ["Compute", "Select", "Join", "Get", "Get"]


@pytest.mark.parametrize(
    "text",
    [
        f"SELECT quantity + 1 AS q, sum(amount / quantity) AS s, count(*) FROM {ORDERS} GROUP BY quantity + 1",
        f"SELECT status, min(order_date), max(amount), avg(quantity) FROM {ORDERS} WHERE amount > 1000 GROUP BY status",
        f"SELECT count(*) AS orders, sum(amount) FROM {ORDERS}",
        f"SELECT order_id, amount * 2 AS doubled FROM {ORDERS} ORDER BY doubled DESC, order_id LIMIT 7",
        f"SELECT * FROM {ORDERS} WHERE NOT status = 'shipped' AND lower(status) != 'returned'",
    ],
)
def test_groups_aggregates_sorts_and_stars_give_duckdbs_rows(text):
    assert same_rows(engine(text), duckdb(text), "order by" in text.lower())


@pytest.mark.parametrize(
    "text, message",
    [
        (f"SELECT nothing FROM {ORDERS}", "no table has a column 'nothing'"),
        (f"SELECT x.order_id FROM {ORDERS} AS o", "no table is called 'x'"),
        (
            f"SELECT customer_id FROM {ORDERS} AS o JOIN 'fixtures/customers.parquet' AS c "
            "ON o.customer_id = c.customer_id",
            "'customer_id' is in o and c: say which, as o.customer_id",
        ),
        (
            f"SELECT status, amount FROM {ORDERS} GROUP BY status",
            "amount is neither grouped by nor aggregated",
        ),
        (f"SELECT order_id FROM {ORDERS} ORDER BY amount", "sorts by a column the query hands up"),
    ],
)
def test_binding_names_the_name_it_cannot_bind(text, message):
    with pytest.raises(planner.PlanError, match=message):
        planner.plan(ROOT, text)


def test_a_limit_keeps_the_first_rows_as_they_come():
    # The engine has no limit of its own, which is problem 3.3's: the planner runs a top-k with
    # no keys, which keeps the first rows it is given.
    text = f"SELECT order_id FROM {ORDERS} LIMIT 7"
    first = pq.read_table(ROOT / "fixtures" / "orders-sorted.parquet", columns=["order_id"])
    assert engine(text) == [(v,) for v in first.column(0).to_pylist()[:7]]
    assert planner.plan(ROOT, text).metrics.operator == "TopK"
