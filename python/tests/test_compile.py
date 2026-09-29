"""A pipeline compiled into one loop, against the same pipeline interpreted (ch19)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from query_lab import compile as compiling
from query_lab.operators import Scan
from query_lab.reference import connect, read_query

ROOT = Path(__file__).resolve().parents[2]
#: Queries of one table with filters and computed columns: a pipeline each.
PIPELINES = ["returned_unit_price.sql", "with_tax.sql", "lower_status.sql", "pricier_returns.sql"]
WAYS = [compiling.compiled, compiling.interpreted, compiling.rows_at_a_time]


def batches(pipeline):
    return list(Scan(ROOT / "fixtures" / "orders-sorted.parquet", pipeline.columns()).batches())


def rounded(rows):
    return sorted(tuple(round(v, 6) if isinstance(v, float) else v for v in r) for r in rows)


@pytest.mark.parametrize("query", PIPELINES)
@pytest.mark.parametrize("way", WAYS, ids=lambda w: w.__name__)
def test_every_way_gives_duckdbs_rows(query, way):
    text = read_query(ROOT / "queries" / query)
    pipeline = compiling.Pipeline.of(text)
    run = way(pipeline, batches(pipeline))
    assert rounded(tuple(r.values()) for r in run.result.to_pylist()) == rounded(
        connect().execute(text).fetchall()
    )


@pytest.mark.parametrize("query", PIPELINES)
def test_the_compiled_loop_visits_no_node_and_writes_only_the_result(query):
    pipeline = compiling.Pipeline.of(read_query(ROOT / "queries" / query))
    run = compiling.compiled(pipeline, batches(pipeline))
    assert run.dispatches == 0
    assert run.written == run.result.get_total_buffer_size()
    assert compiling.interpreted(pipeline, batches(pipeline)).written > run.written


def test_the_generated_code_is_one_loop_that_computes_a_shared_value_once():
    pipeline = compiling.Pipeline.of(read_query(ROOT / "queries" / "returned_unit_price.sql"))
    source = compiling.generate(pipeline).source
    tree = ast.parse(source)
    assert sum(isinstance(n, ast.For) for n in ast.walk(tree)) == 1
    assert source.count("divide(") == 1
    # A row at a time, the interpreter divides again for the output: more instructions.
    rows = batches(pipeline)
    assert (
        compiling.compiled(pipeline, rows).instructions
        < compiling.rows_at_a_time(pipeline, rows).instructions
    )


def test_a_kernel_uses_every_lane_and_a_loop_one():
    pipeline = compiling.Pipeline.of(read_query(ROOT / "queries" / "returned_unit_price.sql"))
    rows = batches(pipeline)
    assert (
        compiling.interpreted(pipeline, rows).instructions < compiling.compiled(pipeline, rows).instructions
    )
