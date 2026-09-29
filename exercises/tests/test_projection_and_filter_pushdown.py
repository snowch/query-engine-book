"""Graders for ch03's problems. Each expected answer is derived at test time: by trying every
value in a range, from the files' own rows and statistics, or from DuckDB. None is stored."""

from __future__ import annotations

import datetime as dt
import operator
from pathlib import Path

import projection_and_filter_pushdown
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest
from parquet_lab import prune
from projection_and_filter_pushdown import Limit, could_match, returned_unit_price_pushed

from query_lab.operators import Comparison, Filter, Scan
from query_lab.plans import EARLY_MARCH, early_march
from query_lab.reference import connect, observe, read_query

ROOT = Path(__file__).resolve().parents[2]
FILES = [ROOT / "fixtures" / f for f in ("orders-sorted.parquet", "orders-shuffled.parquet")]
SORTED = FILES[0]
OPS = {
    "=": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


def refuse(monkeypatch):
    """Make the book's own statistics test fail if the answer calls it."""

    def refused(*args, **kwargs):
        raise AssertionError("this problem asks you to write the test yourself")

    monkeypatch.setattr(prune, "against_bounds", refused)
    monkeypatch.setattr(Comparison, "against_statistics", refused)


def row_group_bounds(path: Path, column: str) -> list[tuple[object, object, list]]:
    """Each row group's smallest and largest value of ``column``, and its values, from the file."""
    file = pq.ParquetFile(path)
    index = file.schema_arrow.get_field_index(column)
    out = []
    for i in range(file.metadata.num_row_groups):
        st = file.metadata.row_group(i).column(index).statistics
        values = file.read_row_group(i, columns=[column]).column(0).to_pylist()
        out.append((st.min, st.max, values))
    return out


# Problem 3.1 -----------------------------------------------------------------------------------


@pytest.mark.problem("3.1")
def test_problem_3_1_could_match_is_exact_on_every_small_range(monkeypatch):
    """For whole numbers, trying every value in the range gives the one right answer."""
    refuse(monkeypatch)
    for op, test in OPS.items():
        for low in range(-3, 4):
            for high in range(low, low + 5):
                for value in range(-6, 10):
                    want = any(test(v, value) for v in range(low, high + 1))
                    got = could_match(op, value, low, high)
                    assert got == want, f"x {op} {value} for x from {low} to {high}: you said {got}" + (
                        ", which would skip rows that match" if want else ", which reads for nothing"
                    )


@pytest.mark.problem("3.1")
@pytest.mark.parametrize(
    "column, values",
    [
        (
            "order_date",
            [dt.date(2024, 1, 1), dt.date(2024, 3, 1), dt.date(2024, 7, 4), dt.date(2024, 12, 31)],
        ),
        ("status", ["cancelled", "pending", "returned", "shipped", "zzz", "a"]),
        ("amount", [2.0, 100.0, 2400.0, 2496.85, 9999.0]),
        ("order_id", [1, 2000, 2001, 3000, 20000, 20001]),
    ],
)
def test_problem_3_1_could_match_never_skips_a_row_group_holding_a_match(monkeypatch, column, values):
    bounds = [b for path in FILES for b in row_group_bounds(path, column)]
    refuse(monkeypatch)
    for op, test in OPS.items():
        for value in values:
            for low, high, rows in bounds:
                if any(test(v, value) for v in rows if v is not None):
                    assert could_match(op, value, low, high), (
                        f"{column} {op} {value!r} for a row group from {low!r} to {high!r}: you said no, "
                        "and it holds a match"
                    )


@pytest.mark.problem("3.1")
def test_problem_3_1_could_match_skips_what_the_books_scan_skips(monkeypatch):
    """On the sorted file, the chapter's dates rule out every row group the engine's scan skips."""
    scan = early_march(ROOT)
    scan.run()
    bounds = row_group_bounds(FILES[0], "order_date")
    refuse(monkeypatch)
    for index in scan.skipped:
        low, high, _ = bounds[index]
        assert not all(could_match(c.op, c.value, low, high) for c in EARLY_MARCH), (
            f"row group {index}, from {low} to {high}, can be skipped for the chapter's dates"
        )


# Problem 3.2 -----------------------------------------------------------------------------------


def scan_of(plan) -> Scan:
    node = plan
    while node.children:
        node = node.children[0]
    return node


@pytest.fixture(scope="module")
def duckdb_run():
    return observe(read_query(ROOT / "queries" / "returned_unit_price.sql"))


@pytest.mark.problem("3.2")
def test_problem_3_2_the_pushed_plan_returns_duckdbs_rows(duckdb_run):
    plan = returned_unit_price_pushed(ROOT)
    result = plan.run()
    assert [tuple(r.values()) for r in result.to_pylist()] == duckdb_run.rows
    plan.metrics.check()


@pytest.mark.problem("3.2")
def test_problem_3_2_the_scan_hands_up_what_duckdbs_scan_handed_up(duckdb_run):
    plan = returned_unit_price_pushed(ROOT)
    plan.run()
    scan = scan_of(plan)
    assert isinstance(scan, Scan), "the plan's bottom operator is a Scan"
    assert any(f.column == "status" for f in scan.filters), "the scan tests the status itself"
    duck = list(duckdb_run.metrics.walk())[-1]
    assert scan.metrics.rows_out == duck.rows_out, (
        f"your scan handed up {scan.metrics.rows_out:,} rows; DuckDB's handed up {duck.rows_out:,}"
    )
    assert "status" not in scan.columns, "nothing above the scan needs the status: do not hand it up"


@pytest.mark.problem("3.2")
def test_problem_3_2_only_the_unit_price_waits_for_a_filter():
    plan = returned_unit_price_pushed(ROOT)
    filters = []
    node = plan
    while node.children:
        if isinstance(node, Filter):
            filters.append(node)
        node = node.children[0]
    assert len(filters) == 1, f"one filter above the scan, for the unit price: you have {len(filters)}"
    assert "status" not in filters[0].metrics.detail, "the status test belongs in the scan"


def limit_rows(sql: str) -> list[tuple]:
    return connect().execute(sql.replace("ORDERS", f"read_parquet('{SORTED}')")).fetchall()


def group_sizes() -> list[int]:
    md = pq.ParquetFile(SORTED).metadata
    return [md.row_group(i).num_rows for i in range(md.num_row_groups)]


def batches_needed(rows_per_batch: list[int], n: int) -> int:
    """The fewest batches, taken in order, that hold ``n`` rows (all of them if there are fewer)."""
    if n == 0:
        return 0
    total = 0
    for i, rows in enumerate(rows_per_batch):
        total += rows
        if total >= n:
            return i + 1
    return len(rows_per_batch)


# Problem 3.3 -----------------------------------------------------------------------------------

LIMITS = [0, 1, 7, 1999, 2000, 2001, 4500, 19999, 20000, 25000]


@pytest.mark.problem("3.3")
@pytest.mark.parametrize("n", LIMITS)
def test_problem_3_3_a_limit_returns_duckdbs_first_rows(n):
    plan = Limit(Scan(SORTED, ["order_id", "amount"]), n)
    got = [tuple(r.values()) for r in plan.run().to_pylist()]
    assert got == limit_rows(f"SELECT order_id, amount FROM ORDERS LIMIT {n}")
    plan.metrics.check()


@pytest.mark.problem("3.3")
@pytest.mark.parametrize("n", LIMITS)
def test_problem_3_3_a_limit_stops_asking_once_it_has_enough(n):
    scan = Scan(SORTED, ["order_id"])
    plan = Limit(scan, n)
    plan.run()
    want = batches_needed(group_sizes(), n)
    assert scan.metrics.batches_out == want, (
        f"the scan produced {scan.metrics.batches_out} batches for a limit of {n}; it needed "
        f"{want}. A limit stops pulling from its child once it holds n rows."
    )
    assert plan.metrics.rows_out == min(n, sum(group_sizes()))


@pytest.mark.problem("3.3")
def test_problem_3_3_a_limit_above_a_filter_pulls_only_what_it_needs():
    scan = Scan(SORTED, ["order_id", "status"])
    returned = Filter(scan, "status = 'returned'", lambda b: pc.equal(b["status"], "returned"))
    plan = Limit(returned, 250)
    got = [tuple(r.values()) for r in plan.run().to_pylist()]
    assert got == limit_rows("SELECT order_id, status FROM ORDERS WHERE status = 'returned' LIMIT 250")
    # How many returned orders each row group holds, from the file itself.
    table = pq.read_table(SORTED, columns=["status"])
    per_group, start = [], 0
    for rows in group_sizes():
        per_group.append(pc.sum(pc.equal(table["status"].slice(start, rows), "returned")).as_py())
        start += rows
    assert scan.metrics.batches_out == batches_needed(per_group, 250)
    plan.metrics.check()


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        could_match("=", 1, 0, 2)
    with pytest.raises(NotImplementedError):
        returned_unit_price_pushed(ROOT)
    with pytest.raises(NotImplementedError):
        list(Limit(Scan(SORTED, ["order_id"]), 5).batches())


def test_the_graders_expectations_can_be_computed(duckdb_run):
    assert batches_needed(group_sizes(), 0) == 0
    assert batches_needed(group_sizes(), sum(group_sizes()) + 1) == len(group_sizes())
    assert len(row_group_bounds(FILES[0], "order_date")) == pq.ParquetFile(FILES[0]).metadata.num_row_groups
    scan = early_march(ROOT)
    scan.run()
    assert scan.skipped, "the sorted file has row groups to skip"
    assert list(duckdb_run.metrics.walk())[-1].rows_out > 0
    assert pc is not None and projection_and_filter_pushdown is not None
