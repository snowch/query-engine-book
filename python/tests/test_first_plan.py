"""ch01's plan, run as the script the page runs: it prints DuckDB's rows and its own counters."""

from __future__ import annotations

import io
import runpy
from contextlib import redirect_stdout
from pathlib import Path

from query_lab.reference import connect, read_query

ROOT = Path(__file__).resolve().parents[2]


def test_the_script_prints_duckdbs_first_rows_and_each_operators_counters(monkeypatch):
    monkeypatch.chdir(ROOT)
    out = io.StringIO()
    with redirect_stdout(out):
        runpy.run_path(str(ROOT / "python" / "query_lab" / "first_plan.py"), run_name="__main__")
    printed = out.getvalue().splitlines()
    theirs = connect().execute(read_query(ROOT / "queries" / "returned_unit_price.sql")).fetchall()
    assert printed[0] == f"{len(theirs):,} rows; the first 5:"
    assert printed[1].split() == ["order_id", "customer_id", "unit_price"]
    for line, row in zip(printed[2:7], theirs, strict=False):
        order_id, customer_id, price = line.split()
        assert (int(order_id), int(customer_id), float(price)) == (row[0], row[1], round(row[2], 3))
    operators = [line.split()[0] for line in printed[9:]]
    assert operators == ["Project", "Filter", "Filter", "Scan"]
