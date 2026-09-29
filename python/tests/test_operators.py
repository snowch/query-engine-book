"""The engine's operators (ch01), held to DuckDB: the same rows, and the same counts where the two
plans do the same job."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pytest

from query_lab.operators import Filter, Project, Scan
from query_lab.plans import DUCKDB_PARTNERS, PLANS, plan_for
from query_lab.reference import observe, read_query

ROOT = Path(__file__).resolve().parents[2]
SORTED = ROOT / "fixtures" / "orders-sorted.parquet"


@pytest.mark.parametrize("query", sorted(PLANS))
def test_every_plan_returns_duckdbs_rows_in_duckdbs_order(query):
    """The same rows as DuckDB, in the same order where the query asks for one. A query with no
    ORDER BY leaves the order to the engine, and a hash aggregate's order is its table's."""
    plan = plan_for(ROOT, query)
    ours = [tuple(row.values()) for row in plan.run().to_pylist()]
    sql = read_query(ROOT / "queries" / query)
    theirs = observe(sql)
    assert plan.schema().names == theirs.columns
    if "ORDER BY" in sql.upper():
        assert ours == theirs.rows
    else:
        assert sorted(ours) == sorted(theirs.rows)


@pytest.mark.parametrize("query", sorted(PLANS))
def test_every_plan_counts_as_duckdb_does_where_they_do_the_same_job(query):
    plan = plan_for(ROOT, query)
    plan.run()
    plan.metrics.check()
    theirs = {m.operator: m for m in observe(read_query(ROOT / "queries" / query)).metrics.walk()}
    for ours, partner in zip(plan.metrics.walk(), DUCKDB_PARTNERS[query], strict=True):
        if partner is not None:
            assert (ours.operator, ours.rows_out) == (ours.operator, theirs[partner].rows_out), partner


def test_the_scan_reads_what_the_reader_logged_and_hands_up_a_batch_per_row_group():
    scan = Scan(SORTED, ["order_id", "status"])
    table = scan.run()
    import pyarrow.parquet as pq

    expected = pq.read_table(SORTED, columns=["order_id", "status"])
    assert table.equals(expected), "the Parquet book's reader decodes what pyarrow wrote"
    md = pq.ParquetFile(SORTED).metadata
    assert scan.metrics.batches_out == md.num_row_groups
    assert scan.metrics.rows_in == scan.metrics.rows_out == md.num_rows
    # The footer takes requests of its own, then one per column per row group.
    assert scan.metrics.requests > 2 * md.num_row_groups
    assert 0 < scan.metrics.bytes_read < SORTED.stat().st_size, "two of seven columns, not the file"


def test_the_scan_reads_nulls_and_dates():
    scan = Scan(SORTED, ["order_date", "note"])
    import pyarrow.parquet as pq

    assert scan.run().equals(pq.read_table(SORTED, columns=["order_date", "note"]))


def test_nothing_is_read_until_something_asks():
    """The pull model: building a plan does no work; asking for one batch reads one row group."""
    scan = Scan(SORTED, ["order_id"])
    plan = Filter(scan, "order_id > 0", lambda b: pc.greater(b["order_id"], 0))
    assert scan.metrics.requests == 0
    next(plan.batches())
    assert scan.metrics.batches_out == 1 and plan.metrics.batches_out == 1


def test_a_projection_computes_its_columns_and_keeps_its_rows():
    scan = Scan(SORTED, ["amount", "quantity"])
    plan = Project(scan, {"double": lambda b: pc.multiply(b["amount"], 2)})
    table = plan.run()
    assert table.schema == pa.schema([("double", pa.float64())])
    assert plan.metrics.rows_out == scan.metrics.rows_out
    plan.metrics.check()
