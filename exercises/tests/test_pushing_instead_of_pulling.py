"""Graders for ch18's problems. Each expected answer is derived at test time: from DuckDB, or from
the batches the grader pushed. None is stored."""

from __future__ import annotations

import random
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest
from pushing_instead_of_pulling import Build, Coalesce, Probe

from query_lab.operators import Scan
from query_lab.push import Collect, Exists, Filter, Source, drive
from query_lab.reference import connect, read_query

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"


def built() -> Build:
    build = Build("customer_id")
    drive(Scan(FIXTURES / "customers.parquet", ["customer_id", "country"]), build)
    return build


# Problem 18.1 ----------------------------------------------------------------------------------


@pytest.mark.problem("18.1")
def test_problem_18_1_the_pushed_join_gives_duckdbs_rows():
    build = built()
    assert build.ready, "the build side was told to finish, and is not ready"
    result = Collect()
    probe = Probe(build, "customer_id", result)
    scan = Scan(FIXTURES / "orders-sorted.parquet", ["order_id", "customer_id"])
    drive(scan, probe)
    table = pa.Table.from_batches(result.batches)
    assert table.column_names == ["order_id", "customer_id", "country"]
    ours = sorted(zip(table.column("order_id").to_pylist(), table.column("country").to_pylist(), strict=True))
    theirs = sorted(connect().execute(read_query(ROOT / "queries" / "orders_with_country.sql")).fetchall())
    assert ours == theirs
    for m in (build.metrics, result.metrics):
        m.check()
    assert build.metrics.rows_in == pq.read_metadata(FIXTURES / "customers.parquet").num_rows
    assert probe.metrics.rows_in == scan.metrics.rows_out


@pytest.mark.problem("18.1")
def test_problem_18_1_the_build_side_wants_every_row():
    build = Build("customer_id")
    rows = pa.record_batch({"customer_id": [1, 2], "country": ["a", "b"]})
    assert build.push(rows) is True
    assert build.push(rows) is True
    assert not build.ready


@pytest.mark.problem("18.1")
def test_problem_18_1_the_probe_refuses_to_start_before_the_build_is_ready():
    build = Build("customer_id")
    build.push(pa.record_batch({"customer_id": [1], "country": ["a"]}))
    probe = Probe(build, "customer_id", Collect())
    with pytest.raises(RuntimeError):
        probe.push(pa.record_batch({"order_id": [7], "customer_id": [1]}))


@pytest.mark.problem("18.1")
def test_problem_18_1_the_probe_passes_on_a_sink_that_has_enough():
    probe = Probe(built(), "customer_id", Exists())
    scan = Scan(FIXTURES / "orders-sorted.parquet", ["order_id", "customer_id"])
    drive(scan, probe)
    assert scan.metrics.batches_out == 1, "the scan kept reading after the sink had its answer"


@pytest.mark.problem("18.1")
def test_problem_18_1_duplicate_keys_on_both_sides():
    build = Build("k")
    drive(Source([pa.record_batch({"k": [1, 1, 2], "v": ["x", "y", "z"]})], None), build)
    result = Collect()
    drive(Source([pa.record_batch({"id": [10, 11, 12], "k": [1, 3, 1]})], None), Probe(build, "k", result))
    rows = sorted(pa.Table.from_batches(result.batches).to_pylist(), key=lambda r: (r["id"], r["v"]))
    assert [(r["id"], r["k"], r["v"]) for r in rows] == [
        (10, 1, "x"),
        (10, 1, "y"),
        (12, 1, "x"),
        (12, 1, "y"),
    ]


# Problem 18.2 ----------------------------------------------------------------------------------


def batches_of(sizes: list[int], start: int = 0) -> list[pa.RecordBatch]:
    out, at = [], start
    for n in sizes:
        out.append(pa.record_batch([pa.array(range(at, at + n), pa.int64())], names=["n"]))
        at += n
    return out


@pytest.mark.problem("18.2")
def test_problem_18_2_small_batches_become_large_ones_in_order():
    rng = random.Random(18)
    for _ in range(200):
        size = rng.randint(1, 50)
        sizes = [rng.choice([0, 1, 2, 5, 17, 60]) for _ in range(rng.randint(0, 30))]
        pushed = batches_of(sizes)
        result = Collect()
        coalesce = Coalesce(size, result)
        drive(Source(pushed, pa.schema([("n", pa.int64())])), coalesce)
        got = [b.num_rows for b in result.batches]
        values = [v for b in result.batches for v in b.column("n").to_pylist()]
        assert values == list(range(sum(sizes))), "rows were lost, added or reordered"
        assert all(n >= size for n in got[:-1]), f"a batch went on before it held {size} rows: {got}"
        assert all(n > 0 for n in got), "an empty batch went on"
        assert all(n < size + max(sizes) for n in got), f"a batch was held longer than it needed: {got}"
        result.metrics.check()
        assert coalesce.metrics.rows_in == sum(sizes) == coalesce.metrics.rows_out


@pytest.mark.problem("18.2")
def test_problem_18_2_after_a_selective_filter():
    scan = Scan(FIXTURES / "orders-sorted.parquet", ["order_id", "status"])
    result = Collect()
    coalesce = Coalesce(1000, result)
    keep = Filter("status = 'returned'", lambda b: pc.equal(b["status"], "returned"), coalesce)
    drive(scan, keep)
    assert keep.metrics.batches_out > len(result.batches) >= 1
    assert sum(b.num_rows for b in result.batches) == keep.metrics.rows_out


@pytest.mark.problem("18.2")
def test_problem_18_2_passes_on_a_sink_that_has_enough():
    coalesce = Coalesce(3, Exists())
    answers = [coalesce.push(b) for b in batches_of([1, 1, 1, 1])]
    assert answers[:2] == [True, True], "a coalesce that has pushed nothing yet wants more"
    assert answers[2] is False, "the sink had its row, and the coalesce did not pass that on"
