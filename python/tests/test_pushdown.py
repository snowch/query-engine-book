"""Projection and filters pushed into the scan (ch03)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest

from query_lab import plans, report
from query_lab.operators import KERNELS, Comparison, Scan
from query_lab.reference import bytes_read, connect, observe, read_query

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = report.GATHER_FIXTURES
COMPARISONS = [
    Comparison("order_date", ">=", dt.date(2024, 3, 1)),
    Comparison("order_date", "<", dt.date(2024, 3, 15)),
    Comparison("order_date", "=", dt.date(2024, 7, 4)),
    Comparison("order_date", "!=", dt.date(2024, 1, 1)),
    Comparison("order_date", "<=", dt.date(2024, 1, 1)),
    Comparison("order_date", ">", dt.date(2024, 12, 30)),
    Comparison("amount", ">", 2400.0),
    Comparison("order_id", "<", 3000),
    Comparison("status", "=", "returned"),
    Comparison("customer_id", "=", 17),
]


def sql_of(comparison: Comparison) -> str:
    value = f"DATE '{comparison.value}'" if isinstance(comparison.value, dt.date) else repr(comparison.value)
    return f"{comparison.column} {comparison.op} {value}"


@pytest.mark.parametrize("fixture", FIXTURES)
@pytest.mark.parametrize("comparison", COMPARISONS, ids=str)
def test_a_pushed_comparison_returns_duckdbs_rows(fixture, comparison):
    scan = Scan(ROOT / "fixtures" / fixture, ["order_id"], [comparison])
    ours = scan.run().column("order_id").to_pylist()
    theirs = (
        connect().execute(f"SELECT order_id FROM 'fixtures/{fixture}' WHERE {sql_of(comparison)}").fetchall()
    )
    assert ours == [r[0] for r in theirs]
    scan.metrics.check()


@pytest.mark.parametrize("fixture", FIXTURES)
@pytest.mark.parametrize("comparison", COMPARISONS, ids=str)
def test_the_statistics_never_skip_a_row_group_holding_a_match(fixture, comparison):
    """A wrong skip loses rows; a wrong read only costs bytes. Checked against every row."""
    scan = Scan(ROOT / "fixtures" / fixture, ["order_id"], [comparison])
    scan.run()
    file = pq.ParquetFile(ROOT / "fixtures" / fixture)
    for index in scan.skipped:
        rows = file.read_row_group(index, columns=[comparison.column])
        assert not pc.any(comparison.mask(rows.to_batches()[0])).as_py(), f"row group {index} held a match"


def test_every_comparison_has_a_kernel():
    assert set(KERNELS) == {"=", "!=", "<", "<=", ">", ">="}


@pytest.mark.parametrize("fixture", FIXTURES)
def test_the_early_march_scan_is_duckdbs(fixture):
    sql = read_query(ROOT / "queries" / "early_march.sql").replace("orders-sorted.parquet", fixture)
    plan = plans.early_march(ROOT, fixture)
    ours = plan.run()
    assert [tuple(r.values()) for r in ours.to_pylist()] == connect().execute(sql).fetchall()
    duck = list(observe(sql).metrics.walk())[-1]
    assert plan.metrics.rows_out == duck.rows_out, "the scan hands up the rows DuckDB's scan did"
    assert plan.metrics.bytes_read == bytes_read(sql), "the scan reads the bytes DuckDB reads"
    groups = pq.ParquetFile(ROOT / "fixtures" / fixture).metadata.num_row_groups
    assert plan.metrics.batches_in == groups - len(plan.skipped)
    plan.metrics.check()


def test_pushing_the_filter_skips_row_groups_only_where_the_file_is_sorted():
    by_file = {f: plans.early_march(ROOT, f) for f in FIXTURES}
    for scan in by_file.values():
        scan.run()
    assert by_file["orders-sorted.parquet"].skipped, "the sorted file's statistics rule row groups out"
    assert not by_file["orders-shuffled.parquet"].skipped, "every shuffled row group spans the year"


def test_a_scan_decodes_a_filters_column_and_hands_up_only_the_columns_asked_for():
    scan = plans.early_march(ROOT)
    table = scan.run()
    assert table.column_names == ["order_id", "customer_id", "amount"]
    assert scan.schema().names == table.column_names


def test_pushing_only_the_columns_decodes_every_row():
    plan = plans.early_march_above(
        ROOT, "orders-sorted.parquet", ["order_id", "order_date", "customer_id", "amount"]
    )
    result = plan.run()
    scan = list(plan.metrics.walk())[-1]
    assert (
        scan.rows_out
        == scan.rows_in
        == pq.ParquetFile(ROOT / "fixtures" / "orders-sorted.parquet").metadata.num_rows
    )
    assert result.to_pylist() == plans.early_march(ROOT).run().to_pylist()
    plan.metrics.check()


def test_the_pruning_report_is_the_scans():
    data = report.run(ROOT, {"experiment": "pruning", "query": "early_march.sql"})
    for f in data["files"]:
        scan = plans.early_march(ROOT, f["fixture"])
        scan.run()
        assert [not g["read"] for g in f["row_groups"]] == [
            i in scan.skipped for i in range(len(f["row_groups"]))
        ]
        assert f["row_groups_read"] == scan.metrics.batches_in
        assert f["bytes_read"] == scan.metrics.bytes_read
        for g in f["row_groups"]:
            assert g["min"] <= g["max"]
    assert data["window"]["min_label"] == "2024-03-01" and data["window"]["max_label"] == "2024-03-15"


def test_a_pruning_report_needs_a_scan_with_filters():
    with pytest.raises(report.ReportError):
        report.run(ROOT, {"experiment": "pruning", "query": "returned_unit_price.sql"})
