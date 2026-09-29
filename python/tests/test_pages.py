"""A scan that reads the page index, and fetches and decodes only the pages it keeps (ch04)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest

from query_lab import plans, report
from query_lab.operators import Comparison, Scan
from query_lab.reference import bytes_read, connect, read_query

ROOT = Path(__file__).resolve().parents[2]
PAGED = ROOT / "fixtures" / "orders-paged.parquet"
COMPARISONS = [
    [
        Comparison("order_date", ">=", dt.date(2024, 3, 1)),
        Comparison("order_date", "<", dt.date(2024, 3, 15)),
    ],
    [Comparison("order_date", "=", dt.date(2024, 12, 31))],
    [Comparison("order_date", "<", dt.date(2024, 1, 1))],
    [Comparison("order_id", ">", 19_500)],
    [Comparison("amount", ">", 2400.0)],
    [Comparison("status", "=", "returned"), Comparison("order_date", ">", dt.date(2024, 11, 30))],
]


def sql_of(c: Comparison) -> str:
    value = f"DATE '{c.value}'" if isinstance(c.value, dt.date) else repr(c.value)
    return f"{c.column} {c.op} {value}"


@pytest.mark.parametrize("filters", COMPARISONS, ids=lambda fs: " AND ".join(map(str, fs)))
def test_a_scan_by_page_returns_duckdbs_rows(filters):
    scan = Scan(PAGED, ["order_id", "amount"], filters, page_index=True)
    ours = [tuple(r.values()) for r in scan.run().to_pylist()]
    where = " AND ".join(map(sql_of, filters))
    assert ours == connect().execute(f"SELECT order_id, amount FROM '{PAGED}' WHERE {where}").fetchall()
    scan.metrics.check()


@pytest.mark.parametrize("filters", COMPARISONS, ids=lambda fs: " AND ".join(map(str, fs)))
def test_every_row_that_matches_lies_in_a_page_the_scan_kept(filters):
    """A wrong skip loses rows; a wrong read only costs bytes. Checked against every row."""
    scan = Scan(PAGED, ["order_id"], filters, page_index=True)
    scan.run()
    table = pq.read_table(PAGED)
    mask = filters[0].mask(table)
    for f in filters[1:]:
        mask = pc.and_(mask, f.mask(table))
    kept = scan.kept.get(0, [])
    for row in pc.indices_nonzero(mask).to_pylist():
        assert any(a <= row < b for a, b in kept), f"row {row} matches and was not read"


def test_without_a_page_index_a_scan_by_page_reads_by_row_group():
    for fixture in ("orders-sorted.parquet", "orders-shuffled.parquet"):
        by_page, by_group = plans.early_march_by_page(ROOT, fixture), plans.early_march(ROOT, fixture)
        assert by_page.run().equals(by_group.run())
        assert (by_page.metrics.rows_in, by_page.metrics.bytes_read, by_page.metrics.requests) == (
            by_group.metrics.rows_in,
            by_group.metrics.bytes_read,
            by_group.metrics.requests,
        )


def test_the_page_index_lets_the_scan_read_a_fraction_of_what_duckdb_reads():
    sql = read_query(ROOT / "queries" / "early_march_paged.sql")
    scan = plans.early_march_by_page(ROOT)
    scan.run()
    assert scan.metrics.rows_in < pq.ParquetFile(PAGED).metadata.num_rows
    everything = bytes_read(sql.split("WHERE")[0])
    assert bytes_read(sql) == everything, (
        "DuckDB 1.1.2 reads the whole row group: it does not use the page index"
    )
    assert scan.metrics.bytes_read < everything


def test_the_pruning_report_draws_pages_where_the_scan_reads_them():
    data = report.run(
        ROOT,
        {
            "experiment": "pruning",
            "query": "early_march_paged.sql",
            "fixtures": "orders-sorted.parquet, orders-paged.parquet",
        },
    )
    sorted_file, paged = data["files"]
    assert sorted_file["unit"] == "row group" and paged["unit"] == "page"
    scan = plans.early_march_by_page(ROOT)
    scan.run()
    assert sum(u["rows"] for u in paged["units"]) == pq.ParquetFile(PAGED).metadata.num_rows
    assert sum(u["rows"] for u in paged["units"] if u["read"]) >= scan.metrics.rows_in
    assert paged["units_read"] == sum(u["read"] for u in paged["units"]) > 0
