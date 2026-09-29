#!/usr/bin/env python3
"""Write the book's datasets: seeded, with the properties each chapter needs, by a real writer.

    python3 fixtures/generate.py              # write the fixtures and their manifests
    python3 fixtures/generate.py --check      # fail if the committed files differ from a fresh run
    python3 fixtures/generate.py --rows 5000000 --out _build/large
                                              # the same datasets, larger, for the desk timing labs

Every dataset is generated from a fixed seed with Python's own ``random``, so the same commit
writes the same rows everywhere, and every file is written by pyarrow (pinned in
``requirements.txt``), a production writer. The engine is tested against files it did not write.

Each dataset states its properties in code rather than prose: the order its rows are written
in, how skewed its keys are, how many distinct values each column holds, how many are null. The
manifest beside each file (``<name>.json``) records what the writer and DuckDB report about it,
so a test can check a property instead of trusting a comment. ``fixtures/README.md`` is generated
from the same list.

The first datasets are the ones the pilot chapters need:

- ``orders``, a fact table, written twice: sorted by date, and shuffled. The same rows in two
  orders are the whole of the pruning argument, and of the cache argument in ch02.
- ``orders-paged``, the sorted orders in one row group with a page index (ch04).
- ``customers``, the small dimension table ``orders.customer_id`` points into, with a skewed
  distribution of orders per customer ready for the join and skew chapters.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
PINNED = {"pyarrow": "18.1.0", "duckdb": "1.1.2"}

#: The committed scale: small enough to read in a browser and to keep in git, large enough that a
#: scan has row groups to skip. The desk timing labs pass ``--rows`` for more.
ORDERS = 20_000
ROW_GROUP = 2_000
CUSTOMERS = 1_000
FIRST_DAY = dt.date(2024, 1, 1)
DAYS = 366

#: Each order's quantity, and its unit price, are drawn evenly from these ranges.
QUANTITY = (1, 10)
UNIT_PRICE = (2.0, 250.0)
STATUSES = (("shipped", 70), ("delivered", 20), ("returned", 6), ("cancelled", 3), ("pending", 1))
COUNTRIES = ("DE", "FR", "UK", "US", "PL", "SE", "ES", "IT", "NL", "JP", "BR", "IN")
SEGMENTS = ("consumer", "small business", "enterprise", "public sector")
WORDS = (
    "fragile", "gift", "leave", "with", "neighbour", "call", "before", "delivery", "rear", "door",
    "urgent", "reorder", "same", "as", "last", "time", "no", "invoice", "please", "wrap",
)  # fmt: skip

#: The page size orders-paged aims at, in bytes. The writer checks it once per batch of rows it
#: writes, so pages come out at about a thousand rows each: a few weeks of orders.
PAGE_BYTES = 1024

#: Customer ``k`` (1-based) receives orders in proportion to ``1 / k**SKEW``: a Zipf-like
#: distribution, so a few customers place many orders and most place few.
SKEW = 1.1
#: The share of orders with no delivery note: the column's nulls, for the validity bitmap.
NOTE_NULL = 0.15


@dataclass(frozen=True)
class Fixture:
    name: str
    why: str
    table: pa.Table
    row_group_size: int
    #: What the generator promises about the rows, checked by tests/test_fixtures.py.
    properties: dict
    #: Whether the writer adds a page index (a column index and an offset index per column chunk),
    #: and the size it aims each data page at. None keeps the writer's default.
    page_index: bool = False
    data_page_size: int | None = None
    #: The columns the writer dictionary-encodes. None keeps the writer's default, which is every
    #: column: a column of nearly unique values then gets a dictionary page holding nearly every
    #: value, which any page of it needs.
    dictionary: list[str] | None = None


def orders_rows(n: int, seed: int) -> dict[str, list]:
    """``n`` orders in date order: ids ascending, dates non-decreasing across the year."""
    rng = random.Random(seed)
    weights = [1 / (k**SKEW) for k in range(1, CUSTOMERS + 1)]
    statuses, status_weights = zip(*STATUSES, strict=True)
    rows: dict[str, list] = {
        k: [] for k in ("order_id", "order_date", "customer_id", "status", "quantity", "amount", "note")
    }
    for i in range(n):
        rows["order_id"].append(i + 1)
        rows["order_date"].append(FIRST_DAY + dt.timedelta(days=i * DAYS // n))
        rows["customer_id"].append(rng.choices(range(1, CUSTOMERS + 1), weights)[0])
        rows["status"].append(rng.choices(statuses, status_weights)[0])
        quantity = rng.randint(*QUANTITY)
        rows["quantity"].append(quantity)
        rows["amount"].append(round(quantity * rng.uniform(*UNIT_PRICE), 2))
        if rng.random() < NOTE_NULL:
            rows["note"].append(None)
        else:
            rows["note"].append(" ".join(rng.choices(WORDS, k=rng.randint(2, 6))))
    return rows


ORDERS_SCHEMA = pa.schema(
    [
        pa.field("order_id", pa.int64(), nullable=False),
        pa.field("order_date", pa.date32(), nullable=False),
        pa.field("customer_id", pa.int32(), nullable=False),
        pa.field("status", pa.string(), nullable=False),
        pa.field("quantity", pa.int32(), nullable=False),
        pa.field("amount", pa.float64(), nullable=False),
        pa.field("note", pa.string(), nullable=True),
    ]
)


def orders(n: int, seed: int = 20240101) -> tuple[pa.Table, pa.Table]:
    """The same orders twice: in date order, and shuffled by a seeded permutation."""
    rows = orders_rows(n, seed)
    table = pa.table(rows, schema=ORDERS_SCHEMA)
    order = list(range(n))
    random.Random(seed + 1).shuffle(order)
    return table, table.take(pa.array(order))


def customers(seed: int = 20240102) -> pa.Table:
    rng = random.Random(seed)
    return pa.table(
        {
            "customer_id": list(range(1, CUSTOMERS + 1)),
            "name": [f"customer {k:04d}" for k in range(1, CUSTOMERS + 1)],
            "country": [rng.choice(COUNTRIES) for _ in range(CUSTOMERS)],
            "segment": [rng.choice(SEGMENTS) for _ in range(CUSTOMERS)],
            "signup_date": [
                dt.date(2019, 1, 1) + dt.timedelta(days=rng.randrange(5 * 365)) for _ in range(CUSTOMERS)
            ],
        },
        schema=pa.schema(
            [
                pa.field("customer_id", pa.int32(), nullable=False),
                pa.field("name", pa.string(), nullable=False),
                pa.field("country", pa.string(), nullable=False),
                pa.field("segment", pa.string(), nullable=False),
                pa.field("signup_date", pa.date32(), nullable=False),
            ]
        ),
    )


def fixtures(n: int = ORDERS, row_group: int = ROW_GROUP) -> list[Fixture]:
    sorted_orders, shuffled_orders = orders(n)
    common = {"rows": n, "row_group_size": row_group, "customers": CUSTOMERS, "customer_skew": SKEW}
    return [
        Fixture(
            "orders-sorted",
            "Orders written in date order. Each row group holds a narrow run of dates, so a filter on "
            "the date can skip most row groups, and neighbouring rows are neighbours in memory.",
            sorted_orders,
            row_group,
            {**common, "sorted_by": ["order_date", "order_id"]},
        ),
        Fixture(
            "orders-shuffled",
            "The same orders in a seeded random order. Every row group spans the whole year, so no "
            "filter on the date can skip one: the control for orders-sorted.",
            shuffled_orders,
            row_group,
            {**common, "sorted_by": []},
        ),
        Fixture(
            "orders-paged",
            "The sorted orders in one row group, with a page index and small pages, and a "
            "dictionary only for the columns with few distinct values. Its one row group spans the "
            "year, so row group statistics can skip nothing; its pages each hold a few weeks, so a "
            "reader that uses the page index can skip most of them.",
            sorted_orders,
            n,
            {
                **common,
                "row_group_size": n,
                "sorted_by": ["order_date", "order_id"],
                "page_index": True,
                "dictionary": ["order_date", "customer_id", "status", "quantity"],
            },
            page_index=True,
            data_page_size=PAGE_BYTES,
            dictionary=["order_date", "customer_id", "status", "quantity"],
        ),
        Fixture(
            "customers",
            "The dimension table orders.customer_id points into: one row per customer, small enough "
            "to be the build side of any join.",
            customers(),
            CUSTOMERS,
            {"rows": CUSTOMERS, "sorted_by": ["customer_id"]},
        ),
    ]


def write(f: Fixture, out: Path) -> None:
    pages = {"data_page_size": f.data_page_size} if f.data_page_size is not None else {}
    if f.dictionary is not None:
        pages["use_dictionary"] = f.dictionary
    pq.write_table(
        f.table,
        out / f"{f.name}.parquet",
        row_group_size=f.row_group_size,
        compression="snappy",
        write_statistics=True,
        data_page_version="1.0",
        write_page_index=f.page_index,
        **pages,
    )


def manifest(f: Fixture, path: Path) -> dict:
    """What pyarrow and DuckDB report about the written file: the facts tests and figures use."""
    md = pq.ParquetFile(path).metadata
    groups = []
    for i in range(md.num_row_groups):
        rg = md.row_group(i)
        columns = {}
        for c in range(rg.num_columns):
            col = rg.column(c)
            st = col.statistics
            columns[col.path_in_schema] = {
                "compressed_bytes": col.total_compressed_size,
                "uncompressed_bytes": col.total_uncompressed_size,
                "min": _json(st.min) if st is not None and st.has_min_max else None,
                "max": _json(st.max) if st is not None and st.has_min_max else None,
                "null_count": st.null_count if st is not None else None,
            }
        groups.append({"rows": rg.num_rows, "columns": columns})
    con = duckdb.connect()
    con.execute("SET threads = 1")
    table = f"read_parquet('{path}')"
    distinct = {
        name: con.execute(f'SELECT count(DISTINCT "{name}") FROM {table}').fetchone()[0]
        for name in f.table.column_names
    }
    nulls = {name: f.table.column(name).null_count for name in f.table.column_names}
    extra = {}
    if "customer_id" in f.table.column_names and f.name.startswith("orders"):
        counts = Counter(f.table.column("customer_id").to_pylist())
        extra["top_customer_orders"] = counts.most_common(1)[0][1]
        extra["customers_with_orders"] = len(counts)
    return {
        "name": f.name,
        "why": f.why,
        "writer": md.created_by,
        "file_bytes": path.stat().st_size,
        "rows": md.num_rows,
        "row_groups": groups,
        "schema": [
            {"name": fld.name, "type": str(fld.type), "nullable": fld.nullable} for fld in f.table.schema
        ],
        "distinct": distinct,
        "nulls": nulls,
        "properties": {**f.properties, **extra},
    }


def _json(v: object) -> object:
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode()
    return v


def readme(entries: list[dict]) -> str:
    rows = "\n".join(
        f"| `{e['name']}.parquet` | {e['rows']:,} | {len(e['row_groups'])} | {e['file_bytes']:,} | {e['why']} |"
        for e in entries
    )
    return f"""# Fixtures

Written by `fixtures/generate.py` with pyarrow {PINNED["pyarrow"]}; described by pyarrow and DuckDB
{PINNED["duckdb"]} in the manifest beside each file. Do not edit by hand: change the generator, run
`make fixtures`, and commit the files, the manifests and this page together.

| File | Rows | Row groups | Bytes | Why it exists |
|---|---:|---:|---:|---|
{rows}
"""


def generate(out: Path, n: int, row_group: int) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    for f in fixtures(n, row_group):
        write(f, out)
        entry = manifest(f, out / f"{f.name}.parquet")
        (out / f"{f.name}.json").write_text(json.dumps(entry, indent=2) + "\n")
        entries.append(entry)
    return entries


def check_versions() -> None:
    have = {"pyarrow": pa.__version__, "duckdb": duckdb.__version__}
    if have != PINNED:
        sys.exit(
            f"fixtures are written with {PINNED}; this Python has {have}. pip install -r requirements.txt"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed fixtures are stale")
    parser.add_argument("--rows", type=int, default=ORDERS, help="orders to write (desk labs only)")
    parser.add_argument("--row-group", type=int, default=ROW_GROUP)
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    check_versions()
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            entries = generate(Path(tmp), ORDERS, ROW_GROUP)
            stale = []
            for e in entries:
                for suffix in (".parquet", ".json"):
                    fresh = (Path(tmp) / f"{e['name']}{suffix}").read_bytes()
                    committed = HERE / f"{e['name']}{suffix}"
                    if not committed.exists() or committed.read_bytes() != fresh:
                        stale.append(committed.name)
            if (HERE / "README.md").read_text() != readme(entries):
                stale.append("README.md")
        if stale:
            print("stale fixtures (run `make fixtures` and commit):", ", ".join(stale))
            return 1
        print(f"  {len(entries)} fixtures match the generator")
        return 0
    entries = generate(args.out, args.rows, args.row_group)
    if args.out.resolve() == HERE:
        (HERE / "README.md").write_text(readme(entries))
    for e in entries:
        print(f"wrote {e['name']}.parquet: {e['rows']} rows, {len(e['row_groups'])} row groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
