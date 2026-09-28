"""Graders for ch02's problems. Each expected answer is derived at test time, from the input array
and its buffers, never stored."""

from __future__ import annotations

import random
from pathlib import Path

import batches_in_memory
import pyarrow as pa
import pyarrow.compute as pc
import pytest
from batches_in_memory import compact, gather_in_order

from query_lab import memory
from query_lab.cache import Cache
from query_lab.operators import Scan
from query_lab.plans import in_date_order

ROOT = Path(__file__).resolve().parents[2]
SHUFFLED = ROOT / "fixtures" / "orders-shuffled.parquet"


def refuse(monkeypatch, *names):
    """Make each named function fail if the answer calls it, wherever the answer finds it."""

    def refused(*args, **kwargs):
        raise AssertionError("this problem asks you to do this by hand")

    for owner, name in names:
        monkeypatch.setattr(owner, name, refused)
        monkeypatch.setattr(batches_in_memory, name, refused, raising=False)


def slices() -> list[pa.Array]:
    """int64 arrays with and without nulls, sliced at every offset within a byte and beyond."""
    rng = random.Random(2)
    with_nulls = pa.array(
        [None if rng.random() < 0.3 else rng.randrange(-(2**40), 2**40) for _ in range(90)], pa.int64()
    )
    no_nulls = pa.array(list(range(1000, 1090)), pa.int64())
    out = []
    for parent in (with_nulls, no_nulls):
        for offset in (0, 1, 3, 7, 8, 9, 15, 16, 17, 30):
            for length in (0, 1, 5, 8, 13, 40):
                out.append(parent.slice(offset, length))
    return out


# Problem 2.1 -----------------------------------------------------------------------------------


@pytest.mark.problem("2.1")
def test_problem_2_1_compact_keeps_the_values_and_the_nulls(monkeypatch):
    arrays = slices()
    expected = [a.to_pylist() for a in arrays]
    builders = [(memory, n) for n in memory.__all__ if n != "FIXED"]
    refuse(monkeypatch, (pa, "array"), (pa, "concat_arrays"), (pc, "take"), *builders)
    for a, want in zip(arrays, expected, strict=True):
        got = compact(a)
        assert got.type == pa.int64(), f"compact returned a {got.type} array"
        assert got.to_pylist() == want, f"a slice at offset {a.offset}, {len(a)} rows, came back different"
        assert got.null_count == a.null_count


@pytest.mark.problem("2.1")
def test_problem_2_1_compact_starts_at_its_first_row():
    for a in slices():
        got = compact(a)
        got.validate(full=True)
        assert got.offset == 0, "the copy's first row must be at the start of its buffers"


@pytest.mark.problem("2.1")
def test_problem_2_1_compact_holds_nothing_but_its_own_rows():
    for a in slices():
        bitmap, values = compact(a).buffers()
        assert values.size == 8 * len(a), (
            f"{len(a)} rows need {8 * len(a)} bytes of values, not {values.size}"
        )
        if a.null_count == 0:
            assert bitmap is None, "an array with no nulls needs no bitmap"
            continue
        assert bitmap is not None, "an array with nulls needs its bitmap"
        assert bitmap.size == (len(a) + 7) // 8, f"{len(a)} rows need {(len(a) + 7) // 8} bytes of bitmap"
        spare = len(a) % 8
        if spare:
            assert bitmap.to_pybytes()[-1] >> spare == 0, "the bits past the last row must be zero"


# Problem 2.2 -----------------------------------------------------------------------------------


class Recording(Cache):
    """The book's cache, keeping every read it was asked for."""

    def __init__(self) -> None:
        super().__init__()
        self.log: list[tuple[str, int, int]] = []

    def read(self, buffer: str, offset: int, size: int) -> None:
        self.log.append((buffer, offset, size))
        super().read(buffer, offset, size)


def gathers() -> list[tuple[str, pa.Array, list[int]]]:
    rng = random.Random(3)
    table = Scan(SHUFFLED, ["order_id", "order_date", "amount", "quantity"]).run()
    amount = table.column("amount").combine_chunks()
    quantity = table.column("quantity").combine_chunks()
    dates = in_date_order(table)
    small = pa.array(list(range(500)), pa.int64()).slice(37, 300)
    return [
        ("amount, in date order", amount, dates),
        ("quantity, in date order", quantity, dates),
        ("amount, backwards", amount, list(range(len(amount) - 1, -1, -1))),
        ("amount, with repeats", amount, [rng.randrange(len(amount)) for _ in range(5000)]),
        ("a slice, shuffled", small, rng.sample(range(len(small)), len(small))),
        ("nothing", amount, []),
    ]


@pytest.fixture(scope="module")
def cases():
    return gathers()


@pytest.mark.problem("2.2")
def test_problem_2_2_reading_in_order_gives_the_gathers_result(cases, monkeypatch):
    expected = [array.take(pa.array(indices, pa.int64())).to_pylist() for _, array, indices in cases]
    refuse(monkeypatch, (memory, "gather"), (pc, "take"))
    for (name, array, indices), want in zip(cases, expected, strict=True):
        got = gather_in_order(array, indices, Cache())
        assert got.to_pylist() == want, f"{name}: wrong result"


@pytest.mark.problem("2.2")
def test_problem_2_2_every_read_is_in_storage_order(cases, monkeypatch):
    refuse(monkeypatch, (memory, "gather"), (pc, "take"))
    for name, array, indices in cases:
        cache = Recording()
        gather_in_order(array, indices, cache)
        width = memory.FIXED[array.type][0]
        assert len(cache.log) == len(indices), (
            f"{name}: {len(cache.log)} reads for {len(indices)} rows asked for"
        )
        assert all(b == "values" and s == width for b, _, s in cache.log), (
            f'{name}: read each row as cache.read("values", byte_offset, {width})'
        )
        offsets = [o for _, o, _ in cache.log]
        assert offsets == sorted(offsets), f"{name}: the reads went back to an earlier row"
        wanted = sorted((array.offset + i) * width for i in indices)
        assert offsets == wanted, f"{name}: the reads are not the rows asked for (mind array.offset)"


@pytest.mark.problem("2.2")
def test_problem_2_2_each_line_is_fetched_once(cases, monkeypatch):
    refuse(monkeypatch, (memory, "gather"), (pc, "take"))
    for name, array, indices in cases:
        cache = Cache()
        gather_in_order(array, indices, cache)
        width = memory.FIXED[array.type][0]
        lines = {(array.offset + i) * width // cache.line_bytes for i in indices}
        assert cache.misses == len(lines), (
            f"{name}: the rows asked for lie in {len(lines)} lines, and the cache fetched {cache.misses}"
        )


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        compact(pa.array([1, 2, 3], pa.int64()))
    with pytest.raises(NotImplementedError):
        gather_in_order(pa.array([1, 2, 3], pa.int64()), [2, 0], Cache())


def test_the_graders_expectations_can_be_computed(cases):
    assert any(a.offset % 8 and a.null_count and len(a) % 8 for a in slices()), (
        "a slice that tests every edge"
    )
    assert {n for n, _, _ in cases} >= {"amount, in date order", "nothing"}
    assert set(memory.__all__) >= {
        "gather",
        "array_from",
        "fixed_width_array",
        "string_array",
        "validity_bitmap",
    }
