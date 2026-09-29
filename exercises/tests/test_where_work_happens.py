"""Graders for ch05's problems. Each expected answer is derived at test time: from the table's own
files, read row by row, or by trying every day. None is stored."""

from __future__ import annotations

import datetime as dt
import json
import operator
import random
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import where_work_happens
from parquet_lab import prune
from where_work_happens import files_to_open, months_to_read

from query_lab.operators import Comparison, TableScan

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "fixtures" / "orders-by-month"
OPS = {
    "=": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}
COMPARISONS = [
    [("order_date", ">=", dt.date(2024, 3, 1)), ("order_date", "<", dt.date(2024, 3, 15))],
    [("order_date", "=", dt.date(2024, 12, 31))],
    [("order_date", "!=", dt.date(2024, 7, 4))],
    [("order_id", "<=", 1694)],
    [("order_id", ">", 18_000), ("order_date", "<", dt.date(2024, 12, 1))],
    [("customer_id", "=", 17)],
    [("customer_id", ">", 999)],
    [("amount", ">", 2490.0)],
    [("status", "=", "returned")],
    [("status", ">", "zzz")],
]


def metadata() -> dict:
    return json.loads((TABLE / "metadata.json").read_text())


def holds(path: str, comparisons) -> bool:
    """Whether the file holds a row passing every comparison: read row by row."""
    rows = pq.read_table(TABLE / path).to_pylist()
    return any(all(OPS[op](r[c], v) for c, op, v in comparisons) for r in rows)


def could_hold(path: str, comparisons) -> bool:
    """Whether some value between each column's smallest and largest in the file could pass every
    comparison on that column: the least a reader of bounds must open. Tried value by value for
    whole numbers and days; for other types, a comparison is ruled out only by the bounds alone."""
    table = pq.read_table(TABLE / path)
    for column in {c for c, _, _ in comparisons}:
        values = [v for v in table.column(column).to_pylist() if v is not None]
        low, high = min(values), max(values)
        tests = [(op, v) for c, op, v in comparisons if c == column]
        if isinstance(low, int) and not isinstance(low, bool):
            candidates = range(low, high + 1)
        elif isinstance(low, dt.date):
            candidates = [low + dt.timedelta(days=d) for d in range((high - low).days + 1)]
        else:
            candidates = None
        if candidates is not None:
            if not any(all(OPS[op](x, v) for op, v in tests) for x in candidates):
                return False
        else:
            for op, v in tests:
                ruled_out = {
                    "=": v < low or v > high,
                    "!=": low == high == v,
                    "<": low >= v,
                    "<=": low > v,
                    ">": high <= v,
                    ">=": high < v,
                }[op]
                if ruled_out:
                    return False
    return True


def refuse(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("this problem asks you to decide from the bounds yourself")

    monkeypatch.setattr(TableScan, "ruled_out", refused)
    monkeypatch.setattr(Comparison, "against_bounds", refused)
    monkeypatch.setattr(prune, "against_bounds", refused)
    monkeypatch.setattr(where_work_happens, "prune", None, raising=False)


# Problem 5.1 -----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def expected():
    paths = [e["path"] for e in metadata()["files"]]
    return {
        i: ([p for p in paths if holds(p, cs)], [p for p in paths if could_hold(p, cs)])
        for i, cs in enumerate(COMPARISONS)
    }


@pytest.mark.problem("5.1")
def test_problem_5_1_every_file_holding_a_match_is_opened(expected, monkeypatch):
    md = metadata()
    refuse(monkeypatch)
    for i, comparisons in enumerate(COMPARISONS):
        must, _ = expected[i]
        got = files_to_open(md, comparisons)
        missing = [p for p in must if p not in got]
        assert not missing, f"{comparisons}: you skipped {missing}, which hold matches"


@pytest.mark.problem("5.1")
def test_problem_5_1_no_file_is_opened_that_its_bounds_rule_out(expected, monkeypatch):
    md = metadata()
    refuse(monkeypatch)
    for i, comparisons in enumerate(COMPARISONS):
        _, may = expected[i]
        got = files_to_open(md, comparisons)
        assert got == may, f"{comparisons}: you open {len(got)} files; the bounds allow exactly {len(may)}"


# Problem 5.2 -----------------------------------------------------------------------------------


def month_holds(path: str, start: dt.date, end: dt.date) -> bool:
    """Whether the file's month holds a day in the range: tried day by day."""
    month = path.split("/")[0].split("=")[1]
    first = dt.date.fromisoformat(month + "-01")
    days = [
        first + dt.timedelta(days=d) for d in range(31) if (first + dt.timedelta(days=d)).month == first.month
    ]
    return any(start <= d < end for d in days)


@pytest.mark.problem("5.2")
def test_problem_5_2_months_to_read_keeps_exactly_the_months_the_range_touches():
    paths = [e["path"] for e in metadata()["files"]]
    rng = random.Random(5)
    cases = [(dt.date(2024, 3, 1), dt.date(2024, 3, 15)), (dt.date(2024, 3, 1), dt.date(2024, 4, 1))]
    cases += [(dt.date(2024, 2, 29), dt.date(2024, 3, 1)), (dt.date(2023, 12, 1), dt.date(2025, 1, 1))]
    cases += [(dt.date(2024, 5, 1), dt.date(2024, 5, 1)), (dt.date(2025, 1, 1), dt.date(2025, 2, 1))]
    for _ in range(40):
        a = dt.date(2024, 1, 1) + dt.timedelta(days=rng.randrange(366))
        cases.append((a, a + dt.timedelta(days=rng.randrange(0, 90))))
    for start, end in cases:
        want = [p for p in paths if month_holds(p, start, end)]
        got = months_to_read(paths, start, end)
        assert got == want, f"{start} to {end}: you read {got}, not {want}"


@pytest.mark.problem("5.2")
def test_problem_5_2_the_months_read_hold_every_matching_row():
    paths = [e["path"] for e in metadata()["files"]]
    start, end = dt.date(2024, 3, 1), dt.date(2024, 3, 15)
    got = months_to_read(paths, start, end)
    for p in paths:
        if holds(p, [("order_date", ">=", start), ("order_date", "<", end)]):
            assert p in got, f"{p} holds rows in the range"


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        files_to_open(metadata(), COMPARISONS[0])
    with pytest.raises(NotImplementedError):
        months_to_read(["month=2024-03/part-0.parquet"], dt.date(2024, 3, 1), dt.date(2024, 3, 2))


def test_the_graders_expectations_can_be_computed():
    paths = [e["path"] for e in metadata()["files"]]
    assert holds("month=2024-03/part-0.parquet", COMPARISONS[0])
    assert not could_hold("month=2024-01/part-0.parquet", COMPARISONS[0])
    assert month_holds("month=2024-02/part-0.parquet", dt.date(2024, 2, 29), dt.date(2024, 3, 1))
    assert len(paths) == len(list(TABLE.rglob("*.parquet")))
