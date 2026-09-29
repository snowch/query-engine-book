"""The fixtures have the properties the generator promises, checked against the files themselves."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"


def manifest(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def test_sorted_and_shuffled_hold_the_same_rows():
    a = pq.read_table(FIXTURES / "orders-sorted.parquet")
    b = pq.read_table(FIXTURES / "orders-shuffled.parquet")
    assert a.num_rows == b.num_rows
    assert a.equals(b.sort_by("order_id"))
    assert not a.equals(b), "the shuffled file must not be in order"


def test_the_sorted_file_is_sorted_and_its_row_groups_do_not_overlap():
    m = manifest("orders-sorted")
    ranges = [(g["columns"]["order_date"]["min"], g["columns"]["order_date"]["max"]) for g in m["row_groups"]]
    assert all(lo <= hi for lo, hi in ranges)
    assert all(ranges[i][1] <= ranges[i + 1][0] for i in range(len(ranges) - 1))


def test_every_shuffled_row_group_spans_nearly_the_whole_year():
    m = manifest("orders-shuffled")
    first, last = (
        min(g["columns"]["order_date"]["min"] for g in m["row_groups"]),
        max(g["columns"]["order_date"]["max"] for g in m["row_groups"]),
    )
    for g in m["row_groups"]:
        assert (
            g["columns"]["order_date"]["min"] < "2024-01-15"
            and g["columns"]["order_date"]["max"] > "2024-12-15"
        )
    assert (first, last) == ("2024-01-01", "2024-12-31")


def test_customer_keys_are_skewed_and_all_point_into_customers():
    orders = pq.read_table(FIXTURES / "orders-sorted.parquet")
    customers = pq.read_table(FIXTURES / "customers.parquet")
    ids = set(customers.column("customer_id").to_pylist())
    assert set(orders.column("customer_id").to_pylist()) <= ids
    counts = pc.value_counts(orders.column("customer_id")).field("counts").to_pylist()
    # A uniform key would give the top customer about rows / customers orders.
    assert max(counts) > 50 * orders.num_rows / len(ids)


@pytest.mark.parametrize(
    "name", ["orders-sorted", "orders-shuffled", "orders-paged", "customers", "countries"]
)
def test_the_manifest_describes_its_file(name):
    m = manifest(name)
    md = pq.ParquetFile(FIXTURES / f"{name}.parquet").metadata
    assert m["rows"] == md.num_rows
    assert len(m["row_groups"]) == md.num_row_groups
    assert m["file_bytes"] == (FIXTURES / f"{name}.parquet").stat().st_size


def test_every_customers_country_is_a_country_with_a_region():
    countries = pq.read_table(FIXTURES / "countries.parquet")
    customers = pq.read_table(FIXTURES / "customers.parquet")
    assert set(customers.column("country").to_pylist()) <= set(countries.column("country").to_pylist())
    assert len(set(countries.column("country").to_pylist())) == countries.num_rows
    assert set(countries.column("region").to_pylist()) == {"Europe", "Americas", "Asia"}


def test_the_note_column_has_nulls_for_the_validity_bitmap():
    m = manifest("orders-sorted")
    assert 0 < m["nulls"]["note"] < m["rows"]


def test_the_paged_file_is_the_sorted_orders_in_one_row_group_with_a_page_index():
    paged = pq.ParquetFile(FIXTURES / "orders-paged.parquet")
    assert paged.read().equals(pq.read_table(FIXTURES / "orders-sorted.parquet"))
    assert paged.metadata.num_row_groups == 1
    for c in range(paged.metadata.num_columns):
        chunk = paged.metadata.row_group(0).column(c)
        assert chunk.has_column_index and chunk.has_offset_index
    dates = manifest("orders-paged")["row_groups"][0]["columns"]["order_date"]
    assert (dates["min"], dates["max"]) == ("2024-01-01", "2024-12-31"), "its one row group spans the year"
