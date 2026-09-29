"""A table of many files read by its metadata, and storage that tests rows itself (ch05)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from query_lab import plans, report
from query_lab.operators import Comparison, TableScan
from query_lab.reference import bytes_read, connect, files_opened, read_query

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "fixtures" / "orders-by-month"
FILTERS = [
    [
        Comparison("order_date", ">=", dt.date(2024, 3, 1)),
        Comparison("order_date", "<", dt.date(2024, 3, 15)),
    ],
    [Comparison("order_date", "=", dt.date(2024, 12, 31))],
    [Comparison("order_id", ">", 19_000)],
    [Comparison("customer_id", "=", 17)],
    [Comparison("amount", ">", 2400.0)],
    [Comparison("status", "=", "returned")],
]


def sql_of(c: Comparison) -> str:
    value = f"DATE '{c.value}'" if isinstance(c.value, dt.date) else repr(c.value)
    return f"{c.column} {c.op} {value}"


@pytest.mark.parametrize("metadata", [True, False])
@pytest.mark.parametrize("filters", FILTERS, ids=lambda fs: " AND ".join(map(str, fs)))
def test_a_table_scan_returns_duckdbs_rows(filters, metadata):
    scan = TableScan(TABLE, ["order_id", "amount"], filters, metadata=metadata)
    ours = [tuple(r.values()) for r in scan.run().to_pylist()]
    where = " AND ".join(map(sql_of, filters))
    theirs = connect().execute(
        f"SELECT order_id, amount FROM read_parquet('{TABLE}/*/*.parquet') WHERE {where} ORDER BY order_id"
    )
    assert sorted(ours) == theirs.fetchall()
    scan.metrics.check()


@pytest.mark.parametrize("filters", FILTERS, ids=lambda fs: " AND ".join(map(str, fs)))
def test_the_metadata_never_skips_a_file_holding_a_match(filters):
    scan = TableScan(TABLE, ["order_id"], filters, metadata=True)
    scan.run()
    for path in scan.skipped:
        rows = pq.read_table(TABLE / path)
        masks = [f.mask(rows).to_pylist() for f in filters]
        assert not any(all(row) for row in zip(*masks, strict=True)), (
            f"{path} held a match and was never opened"
        )


def test_the_metadata_lists_every_file_with_its_own_statistics():
    metadata = json.loads((TABLE / TableScan.METADATA).read_text())
    files = sorted(p.relative_to(TABLE).as_posix() for p in TABLE.rglob("*.parquet"))
    assert [e["path"] for e in metadata["files"]] == files
    for entry in metadata["files"]:
        md = pq.ParquetFile(TABLE / entry["path"]).metadata
        assert entry["rows"] == md.num_rows and entry["bytes"] == (TABLE / entry["path"]).stat().st_size


def test_by_its_files_the_table_scan_reads_what_duckdb_reads():
    sql = read_query(ROOT / "queries" / "early_march_table.sql")
    by_files = plans.early_march_table(ROOT, metadata=False)
    by_files.run()
    assert by_files.metrics.bytes_read == bytes_read(sql)
    assert len(by_files.opened) == files_opened(sql) == len(list(TABLE.rglob("*.parquet")))


def test_by_its_metadata_the_table_scan_opens_only_the_files_that_might_match():
    by_metadata, by_files = plans.early_march_table(ROOT), plans.early_march_table(ROOT, metadata=False)
    assert by_metadata.run().equals(by_files.run())
    assert by_metadata.opened == ["month=2024-03/part-0.parquet"]
    assert by_metadata.metrics.requests < by_files.metrics.requests


@pytest.mark.parametrize("fixture", report.GATHER_FIXTURES)
def test_storage_that_tests_rows_returns_the_scans_rows_and_sends_only_them(fixture):
    in_storage, in_engine = plans.early_march_in_storage(ROOT, fixture), plans.early_march(ROOT, fixture)
    assert in_storage.run().to_pylist() == in_engine.run().to_pylist()
    assert in_storage.metrics.requests == 1
    assert in_storage.storage.bytes_read == in_engine.metrics.bytes_read, (
        "the storage reads what the scan read"
    )
    assert in_storage.metrics.bytes_read < in_engine.metrics.bytes_read
    in_storage.metrics.check()


def test_the_pruning_report_draws_a_tables_files():
    data = report.run(
        ROOT,
        {"experiment": "pruning", "query": "early_march_table.sql", "scans": "by its metadata, by its files"},
    )
    by_metadata, by_files = data["files"]
    assert by_metadata["unit"] == by_files["unit"] == "file"
    assert by_metadata["units_read"] == 1 and by_files["units_read"] == len(by_files["units"])
    assert data["window"]["min_label"] == "2024-03-01"
