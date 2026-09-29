"""Graders for ch04's problems. Each expected answer is derived at test time: by trying every row
or every value, or from the file's own rows and page index. None is stored."""

from __future__ import annotations

import datetime as dt
import operator
import random
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import statistics_and_pruning
from parquet_lab import page_index
from parquet_lab.reader import FooterOptions, read_footer
from parquet_lab.schema import build, leaves
from statistics_and_pruning import kept_rows, pages_for

from query_lab import operators, report
from query_lab.plans import EARLY_MARCH

ROOT = Path(__file__).resolve().parents[2]
PAGED = ROOT / "fixtures" / "orders-paged.parquet"
OPS = {
    "=": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


def refuse(monkeypatch):
    """Make the book's own page test and range arithmetic fail if the answer calls them."""

    def refused(*args, **kwargs):
        raise AssertionError("this problem asks you to write this yourself")

    monkeypatch.setattr(operators.Comparison, "against_page", refused)
    monkeypatch.setattr(operators, "_intersect", refused)
    for name in ("_intersect", "Comparison"):
        monkeypatch.setattr(statistics_and_pruning, name, refused, raising=False)


def random_pages(rng: random.Random, rows: int) -> list[tuple[int, int]]:
    cuts = sorted(rng.sample(range(1, rows), rng.randrange(0, min(12, rows - 1) + 1)))
    edges = [0, *cuts, rows]
    return list(zip(edges, edges[1:], strict=False))


def random_rows(rng: random.Random, rows: int) -> list[tuple[int, int]]:
    out, at = [], 0
    while at < rows:
        start = at + rng.randrange(0, 40)
        end = min(rows, start + rng.randrange(1, 40))
        if start < rows:
            out.append((start, end))
        at = end + rng.randrange(1, 20)
    return out


def paged_date_pages() -> list[dict]:
    """orders-paged's pages of order_date, from its page index, with the rows each holds."""
    data = PAGED.read_bytes()
    md = read_footer(report._store(PAGED), PAGED.name, FooterOptions()).metadata
    leaf = next(x for x in leaves(build(md.schema)) if x.dotted_path() == "order_date")
    group = md.row_groups[0]
    index = page_index.column_index(data, group.columns[leaf.column])
    ranges = page_index.offset_index(data, group.columns[leaf.column]).row_ranges(group.num_rows)
    epoch = dt.date(1970, 1, 1)

    def day(plain: bytes) -> dt.date:
        return epoch + dt.timedelta(days=int.from_bytes(plain, "little", signed=True))

    return [
        {"rows": r, "min": day(index.min_values[i]), "max": day(index.max_values[i])}
        for i, r in enumerate(ranges)
    ]


# Problem 4.1 -----------------------------------------------------------------------------------


@pytest.mark.problem("4.1")
def test_problem_4_1_pages_for_finds_every_page_holding_a_kept_row(monkeypatch):
    rng = random.Random(4)
    cases = [(random_rows(rng, n), random_pages(rng, n)) for n in (1, 7, 50, 300, 1000) for _ in range(20)]
    cases += [([], [(0, 10), (10, 20)]), ([(0, 20)], [(0, 10), (10, 20)]), ([(10, 11)], [(0, 10), (10, 20)])]
    refuse(monkeypatch)
    for rows, pages in cases:
        want = [i for i, (a, b) in enumerate(pages) if any(s <= r < e for r in range(a, b) for s, e in rows)]
        got = pages_for(rows, pages)
        assert got == want, f"rows {rows[:4]}… over pages {pages[:4]}…: you gave {got[:8]}, not {want[:8]}"


@pytest.mark.problem("4.1")
def test_problem_4_1_pages_for_matches_what_the_paged_file_needs(monkeypatch):
    """The chapter's fortnight on orders-paged: the date pages it keeps, then each column's pages."""
    data = PAGED.read_bytes()
    md = read_footer(report._store(PAGED), PAGED.name, FooterOptions()).metadata
    group = md.row_groups[0]
    table = pq.read_table(PAGED)
    rows = [
        (r, r + 1)
        for r, d in enumerate(table.column("order_date").to_pylist())
        if d.month == 3 and d.day < 15
    ]
    refuse(monkeypatch)
    for chunk in group.columns:
        ranges = page_index.offset_index(data, chunk).row_ranges(group.num_rows)
        want = [i for i, (a, b) in enumerate(ranges) if any(a <= s < b for s, _ in rows)]
        assert pages_for(rows, ranges) == want


# Problem 4.2 -----------------------------------------------------------------------------------


def could_hold(page: dict, comparisons: list[tuple[str, object]]) -> bool:
    """Whether some whole number in the page's range passes every comparison: tried one by one."""
    return any(all(OPS[op](v, x) for op, x in comparisons) for v in range(page["min"], page["max"] + 1))


def as_ranges(pages: list[dict]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for p in pages:
        a, b = p["rows"]
        if out and out[-1][1] == a:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


@pytest.mark.problem("4.2")
def test_problem_4_2_kept_rows_keeps_exactly_the_pages_that_could_match(monkeypatch):
    rng = random.Random(42)
    cases = []
    for _ in range(300):
        at, pages = 0, []
        for _ in range(rng.randrange(1, 9)):
            low = rng.randrange(-10, 10)
            size = rng.randrange(1, 30)
            pages.append({"rows": (at, at + size), "min": low, "max": low + rng.randrange(0, 6)})
            at += size
        comparisons = [(rng.choice(list(OPS)), rng.randrange(-12, 16)) for _ in range(rng.randrange(1, 4))]
        cases.append((pages, comparisons))
    cases.append(([{"rows": (0, 10), "min": 1, "max": 10}], [(">", 8), ("<", 3)]))
    expected = [as_ranges([p for p in pages if could_hold(p, cs)]) for pages, cs in cases]
    refuse(monkeypatch)
    for (pages, comparisons), want in zip(cases, expected, strict=True):
        got = kept_rows(pages, comparisons)
        assert got == want, (
            f"{comparisons} over {[(p['min'], p['max']) for p in pages]}: you kept {got}, not {want}"
        )


@pytest.mark.problem("4.2")
def test_problem_4_2_kept_rows_keeps_every_page_holding_a_match_in_the_paged_file(monkeypatch):
    pages = paged_date_pages()
    dates = pq.read_table(PAGED).column("order_date").to_pylist()
    comparisons = [(c.op, c.value) for c in EARLY_MARCH]
    matches = [r for r, d in enumerate(dates) if all(OPS[op](d, x) for op, x in comparisons)]
    refuse(monkeypatch)
    kept = kept_rows(pages, comparisons)
    for row in matches:
        assert any(a <= row < b for a, b in kept), f"row {row} matches and your ranges leave it out"
    assert sum(b - a for a, b in kept) < len(dates), "the page index rules most of the file out"


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        pages_for([(0, 1)], [(0, 1)])
    with pytest.raises(NotImplementedError):
        kept_rows([{"rows": (0, 1), "min": 0, "max": 0}], [("=", 0)])


def test_the_graders_expectations_can_be_computed():
    pages = paged_date_pages()
    assert len(pages) > 1 and pages[0]["rows"][0] == 0
    assert could_hold({"rows": (0, 1), "min": 1, "max": 10}, [(">", 8), ("<", 3)]) is False
    assert as_ranges([{"rows": (0, 2)}, {"rows": (2, 5)}, {"rows": (7, 9)}]) == [(0, 5), (7, 9)]
