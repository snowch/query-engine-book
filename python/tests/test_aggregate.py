"""Grouping by a hash table and by a perfect one, against DuckDB (ch07)."""

from __future__ import annotations

from pathlib import Path

import pytest

from query_lab import plans, report
from query_lab.aggregate import LOAD, SLOT_BYTES, Aggregate, HashAggregate, HashTable, PerfectTable, hash_key
from query_lab.cache import Cache
from query_lab.operators import Scan
from query_lab.reference import connect

ROOT = Path(__file__).resolve().parents[2]
SORTED = ROOT / "fixtures" / "orders-sorted.parquet"
AGGREGATES = [
    Aggregate("n", "count"),
    Aggregate("total", "sum", "quantity"),
    Aggregate("low", "min", "amount"),
    Aggregate("high", "max", "amount"),
    Aggregate("mean", "avg", "quantity"),
]


@pytest.mark.parametrize(
    "keys", [["status"], ["customer_id"], ["order_date"], ["quantity"], ["status", "quantity"]]
)
def test_a_hash_aggregate_returns_duckdbs_groups(keys):
    columns = sorted({*keys, "quantity", "amount"})
    plan = HashAggregate(Scan(SORTED, columns), keys, AGGREGATES)
    ours = sorted(tuple(r.values()) for r in plan.run().to_pylist())
    listed = ", ".join(keys)
    theirs = connect().execute(
        f"SELECT {listed}, count(*), sum(quantity), min(amount), max(amount), avg(quantity) "
        f"FROM '{SORTED}' GROUP BY {listed} ORDER BY {listed}"
    )
    theirs = sorted(theirs.fetchall())
    assert len(ours) == len(theirs)
    for a, b in zip(ours, theirs, strict=True):
        assert a[:-1] == b[:-1]
        assert a[-1] == pytest.approx(b[-1])
    plan.metrics.check()


def test_a_perfect_table_finds_the_same_groups_with_one_probe_a_row():
    hashed, perfect = plans.orders_per_customer(ROOT), plans.orders_per_customer(ROOT, perfect=True)
    assert sorted(hashed.run().to_pylist(), key=str) == sorted(perfect.run().to_pylist(), key=str)
    rows = hashed.metrics.rows_in
    assert perfect.table.probes == perfect.table.lookups == rows
    assert hashed.table.probes > rows, "a hash table's keys collide"
    assert perfect.metrics.operator == "PerfectHashAggregate"


def test_the_table_grows_before_it_is_three_quarters_full_and_probes_at_least_once_a_lookup():
    table = HashTable(capacity=4)
    for k in range(1000):
        group, new = table.find(k)
        assert new and group == k
        assert len(table.keys) <= table.capacity * LOAD
    assert all(table.find(k) == (k, False) for k in range(1000))
    assert table.probes >= table.lookups == 2000
    assert table.table_bytes == table.capacity * SLOT_BYTES


def test_a_key_hashes_the_same_every_time_and_types_do_not_collide_by_accident():
    assert hash_key("returned") == hash_key("returned")
    assert len({hash_key(v) for v in [1, "1", 1.0, (1,), None]}) == 5


def test_a_table_that_fits_the_cache_misses_once_a_line_and_one_that_does_not_misses_most_lookups():
    small, large = Cache(), Cache()
    status = HashTable(cache=small)
    ids = HashTable(cache=large)
    for batch in Scan(SORTED, ["status", "order_id"]).batches():
        for s, i in zip(
            batch.column("status").to_pylist(), batch.column("order_id").to_pylist(), strict=True
        ):
            status.find(s)
            ids.find(i)
    assert small.misses <= status.table_bytes // small.line_bytes
    assert large.misses > ids.lookups // 2


def test_the_aggregation_report_is_the_engines():
    data = report.run(ROOT, {"experiment": "measure", "of": "aggregation"})
    by_key = {c["label"]: c for c in data["cases"]}
    assert by_key["GROUP BY status"]["measured"] < by_key["GROUP BY customer_id"]["measured"]
    assert by_key["GROUP BY customer_id"]["measured"] < by_key["GROUP BY order_id"]["measured"]
    hashed, perfect = data["chart"]["series"]
    assert [p[0] for p in hashed["points"]] == [p[0] for p in perfect["points"]]
    assert all(p[1] <= h[1] for p, h in zip(perfect["points"], hashed["points"], strict=True))


def test_a_perfect_table_takes_its_range_from_the_files_statistics():
    low, high = plans.customer_id_range(SORTED)
    assert (low, high) == tuple(
        connect().execute(f"SELECT min(customer_id), max(customer_id) FROM '{SORTED}'").fetchone()
    )
    assert PerfectTable(low, high).capacity == high - low + 1
