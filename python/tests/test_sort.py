"""A full sort and a top-k, against DuckDB, and what each compares and holds (ch09)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from query_lab import plans, report
from query_lab.operators import Scan
from query_lab.reference import connect
from query_lab.sort import Sort, TopK

ROOT = Path(__file__).resolve().parents[2]
SHUFFLED = ROOT / "fixtures" / "orders-shuffled.parquet"
SORTED = ROOT / "fixtures" / "orders-sorted.parquet"


def duckdb(sql: str) -> list[tuple]:
    return connect().execute(sql).fetchall()


@pytest.mark.parametrize(
    "keys, order_by",
    [
        ([("amount", True), ("order_id", False)], "amount DESC, order_id"),
        ([("status", False), ("amount", False), ("order_id", False)], "status, amount, order_id"),
        ([("order_date", True), ("order_id", True)], "order_date DESC, order_id DESC"),
    ],
)
def test_a_sort_puts_the_rows_in_duckdbs_order(keys, order_by):
    columns = sorted({"order_id", *(c for c, _ in keys)})
    ours = [tuple(r.values()) for r in Sort(Scan(SHUFFLED, columns), keys).run().to_pylist()]
    assert ours == duckdb(f"SELECT {', '.join(columns)} FROM '{SHUFFLED}' ORDER BY {order_by}")


@pytest.mark.parametrize("k", [1, 7, 100, 20_000, 30_000])
def test_a_top_k_is_the_sorts_first_k_rows_and_holds_no_more(k):
    top = TopK(Scan(SHUFFLED, ["order_id", "amount"]), plans.BY_AMOUNT, k)
    ours = [tuple(r.values()) for r in top.run().to_pylist()]
    assert ours == duckdb(
        f"SELECT order_id, amount FROM '{SHUFFLED}' ORDER BY amount DESC, order_id LIMIT {k}"
    )
    assert top.rows_held == min(k, top.metrics.rows_in)


def test_a_sort_of_rows_already_in_order_compares_each_row_once():
    sort = Sort(Scan(SORTED, ["order_id", "order_date"]), [("order_date", False), ("order_id", False)])
    sort.run()
    assert sort.comparisons.count == sort.metrics.rows_in - 1


def test_a_sort_of_shuffled_rows_compares_about_n_log_n_and_a_small_top_k_about_n():
    sort, top = plans.orders_by_amount(ROOT), plans.top_orders(ROOT)
    sort.run()
    top.run()
    n = sort.metrics.rows_in
    assert 0.5 * n * math.log2(n) < sort.comparisons.count < n * math.log2(n)
    assert n <= top.comparisons.count < 1.1 * n


def test_the_sorting_report_is_the_engines():
    data = report.run(ROOT, {"experiment": "measure", "of": "sorting"})
    shuffled, stored, top = data["cases"]
    assert stored["measured"] < top["measured"] < shuffled["measured"]
    heap, full = data["chart"]["series"]
    assert [y for _, y in heap["points"]] == sorted(y for _, y in heap["points"])
    assert heap["points"][-1][1] > full["points"][-1][1], "a heap of every row is worse than a sort"
