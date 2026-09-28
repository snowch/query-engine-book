"""Arrays from raw buffers, validity bits, the cache model and the gather (ch02)."""

from __future__ import annotations

import random
from pathlib import Path

import pyarrow as pa
import pytest

from query_lab import plans, report
from query_lab.cache import Cache
from query_lab.memory import (
    FIXED,
    array_from,
    buffer_sizes,
    fixed_width_array,
    gather,
    is_valid,
    string_array,
    validity_bitmap,
)
from query_lab.operators import Scan
from query_lab.reference import connect, read_query

ROOT = Path(__file__).resolve().parents[2]
VALUES = {
    pa.int32(): [3, None, -7, 2**31 - 1, 0, None, 5, 6, 7, None],
    pa.int64(): [2**40, None, -1, 0, 9, None, None, 1, 2, 3, 4],
    pa.float64(): [1.5, None, -0.25, 1e300, 0.0],
    pa.date32(): [19723, 0, None, 20089],
    pa.string(): ["", "gift", None, "fragile rear door", "é", None, "x"],
}


@pytest.mark.parametrize("kind", list(VALUES), ids=str)
def test_an_array_built_by_hand_is_the_array_pyarrow_builds(kind):
    ours, theirs = array_from(VALUES[kind], kind), pa.array(VALUES[kind], kind)
    ours.validate(full=True)
    assert ours.equals(theirs)
    assert ours.null_count == theirs.null_count
    assert buffer_sizes(ours) == {
        name: None if b is None else b.size
        for name, b in zip(buffer_sizes(ours), theirs.buffers(), strict=True)
    }


def test_an_array_with_no_nulls_has_no_bitmap():
    assert validity_bitmap([1, 2, 3]) is None
    assert fixed_width_array([1, 2, 3], pa.int64()).buffers()[0] is None
    assert string_array(["a", "b"]).buffers()[0] is None


def test_a_bitmap_is_one_bit_per_row_least_significant_first():
    bits = validity_bitmap([1, None, 1, 1, None, None, None, None, 1])
    assert bits.to_pybytes() == bytes([0b00001101, 0b00000001])


def test_a_strings_offsets_bound_its_bytes():
    array = string_array(["ab", None, "", "cde"])
    assert buffer_sizes(array) == {"validity": 1, "offsets": 20, "data": 5}
    assert pa.Array.from_buffers(pa.int32(), 5, [None, array.buffers()[1]]).to_pylist() == [0, 2, 2, 2, 5]


@pytest.mark.parametrize("offset", [0, 1, 3, 7, 8, 9])
def test_validity_is_read_through_a_slices_offset(offset):
    values = [None if i % 3 == 0 else i for i in range(40)]
    array = pa.array(values, pa.int64()).slice(offset, 20)
    assert [is_valid(array, i) for i in range(len(array))] == [
        v is not None for v in values[offset : offset + 20]
    ]


def test_the_cache_counts_lines_and_pushes_out_the_least_recently_used():
    cache = Cache(lines=2, line_bytes=64)
    cache.read("v", 0, 8)  # line 0: miss
    cache.read("v", 56, 16)  # lines 0 and 1: hit, miss
    cache.read("v", 128, 1)  # line 2: miss, pushes out line 0
    cache.read("v", 64, 1)  # line 1: hit
    cache.read("v", 0, 1)  # line 0: miss again
    cache.read("w", 0, 1)  # another buffer's line 0: miss
    assert cache.counters() == {"reads": 6, "hits": 2, "misses": 5, "bytes_fetched": 5 * 64}


@pytest.mark.parametrize("kind", list(VALUES), ids=str)
def test_a_gather_is_a_take(kind):
    array = array_from(VALUES[kind] * 30, kind).slice(5)
    order = random.Random(7).choices(range(len(array)), k=100)
    assert gather(array, order, Cache()).equals(array.take(pa.array(order, pa.int64())))


def test_a_gather_in_storage_order_fetches_each_line_once():
    array = fixed_width_array(list(range(10_000)), pa.int64())
    cache = Cache()
    gather(array, list(range(10_000)), cache)
    assert cache.misses == buffer_sizes(array)["values"] // cache.line_bytes
    assert cache.reads == len(array)


def test_a_gather_in_any_order_fetches_more_once_the_column_outgrows_the_cache():
    array = fixed_width_array(list(range(10_000)), pa.int64())
    order = list(range(10_000))
    random.Random(1).shuffle(order)
    cache = Cache()
    gather(array, order, cache)
    assert cache.misses > 4 * buffer_sizes(array)["values"] // cache.line_bytes


def test_the_scan_builds_the_arrays_the_file_holds():
    ours = Scan(ROOT / "fixtures" / "orders-shuffled.parquet", plans.ORDERS_BY_DATE).run()
    theirs = connect().execute(
        "SELECT * EXCLUDE (customer_id, quantity) FROM 'fixtures/orders-shuffled.parquet'"
    )
    # The scan keeps the file's REQUIRED columns as not null, where DuckDB's result says nothing.
    assert ours.to_pydict() == theirs.arrow().select(plans.ORDERS_BY_DATE).to_pydict()


@pytest.mark.parametrize("fixture", report.GATHER_FIXTURES)
def test_the_date_order_is_duckdbs(fixture):
    table = Scan(ROOT / "fixtures" / fixture, ["order_id", "order_date"]).run()
    sql = read_query(ROOT / "queries" / "orders_by_date.sql").replace("orders-shuffled.parquet", fixture)
    assert plans.in_date_order(table) == [r[0] for r in connect().execute(sql).fetchall()]


def test_the_engines_orders_by_date_returns_duckdbs_result():
    ours, caches = plans.orders_by_date(ROOT)
    theirs = connect().execute(read_query(ROOT / "queries" / "orders_by_date.sql")).arrow()
    assert ours.equals(theirs)
    assert set(caches) == set(plans.ORDERS_BY_DATE)


def test_the_gather_report_is_the_engines_gather():
    data = report.run(ROOT, {"experiment": "gather", "column": "amount"})
    width = FIXED[pa.float64()][0]
    assert data["column_lines"] * data["cache"]["line_bytes"] == data["rows"] * width
    by_file = {f: plans.orders_by_date(ROOT, f)[1]["amount"] for f in report.GATHER_FIXTURES}
    for g in data["gathers"]:
        assert {k: g[k] for k in ("reads", "hits", "misses", "bytes_fetched")} == by_file[
            g["fixture"]
        ].counters()
        assert len(g["pattern"]) == report.PATTERN_READS
    sorted_run, shuffled_run = data["gathers"]
    assert sorted_run["misses"] == data["column_lines"], "in storage order, every line is fetched once"
    assert shuffled_run["misses"] > sorted_run["misses"]


def test_a_gather_report_refuses_a_column_of_strings():
    with pytest.raises(report.ReportError):
        report.run(ROOT, {"experiment": "gather", "column": "status"})
