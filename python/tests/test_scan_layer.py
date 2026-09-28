"""The Parquet book's reader is this book's scan layer, imported from the pinned submodule.

These tests are the desk half of the spike in PLAN.md (Phase 0): the reader imports as a
package, reads the fixtures pyarrow wrote, and its scan agrees with DuckDB about which rows match
a predicate. They also pin what the scan layer reports, which COUNTERS.md builds on: the bytes it
fetched and the requests it made.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import parquet_lab
from parquet_lab.object_store import NetworkModel
from parquet_lab.prune import Op
from parquet_lab.scan import Query, Strategy, scan

ROOT = Path(__file__).resolve().parents[2]
SUBMODULE = ROOT / "external" / "parquet-book" / "python" / "parquet_lab"


def test_the_reader_comes_from_the_submodule_not_a_copy():
    assert Path(parquet_lab.__file__).resolve().parent == SUBMODULE.resolve()
    assert not (ROOT / "python" / "parquet_lab").exists()


def run(name: str, column: int, op: Op, text: str):
    data = (ROOT / "fixtures" / f"{name}.parquet").read_bytes()
    return scan(data, name, Query(columns=[0], condition=(column, op, text)), Strategy(), NetworkModel())


def test_the_scan_matches_duckdb_on_both_orders():
    # Column 0 is order_id; the condition is on it, so the answer is known in advance too.
    for name in ("orders-sorted", "orders-shuffled"):
        result = run(name, 0, Op.LT, "500")
        want = duckdb.sql(
            f"SELECT count(*) FROM read_parquet('{ROOT / 'fixtures' / name}.parquet') WHERE order_id < 500"
        ).fetchone()[0]
        assert len(result.matches) == want == 499


def test_sorted_data_lets_the_scan_read_less():
    """The pilot's third chapter in one assertion: the same rows, the same predicate, fewer bytes."""
    sorted_scan = run("orders-sorted", 0, Op.LT, "500")
    shuffled_scan = run("orders-shuffled", 0, Op.LT, "500")
    assert sorted_scan.bytes_fetched < shuffled_scan.bytes_fetched / 3
    assert sorted_scan.rows_decoded < shuffled_scan.rows_decoded
