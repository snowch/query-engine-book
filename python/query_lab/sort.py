"""Putting rows in order: a full sort, and the top k rows kept in a heap (ch09).

``ORDER BY`` needs every row before it can hand up the first, since the last row read might sort
first. A full sort holds them all and compares them; how many comparisons depends on the
algorithm and on the order the rows arrive in. With a ``LIMIT``, an engine can do much less: to
find the top k rows it keeps only k of them, in a heap, and compares each new row with the worst
row it is keeping. Most rows lose at once.

Both operators count their comparisons, which are the same on every machine for the same rows:
COUNTERS.md, *The simulators' counters*.
"""

from __future__ import annotations

import heapq
from collections.abc import Iterator
from functools import cmp_to_key

import pyarrow as pa

from .operators import Operator


class Comparisons:
    """A count of the comparisons a sort makes, and the comparison itself: rows compared by their
    keys, in the directions the ``ORDER BY`` gives."""

    def __init__(self, descending: list[bool]) -> None:
        self.descending = descending
        self.count = 0

    def compare(self, a: tuple, b: tuple) -> int:
        """Negative if row key ``a`` sorts first, positive if ``b`` does, nought if they tie."""
        self.count += 1
        for x, y, down in zip(a, b, self.descending, strict=True):
            if x != y:
                first = x > y if down else x < y
                return -1 if first else 1
        return 0


def _rows(batch: pa.RecordBatch, keys: list[str]) -> list[tuple]:
    """Each row of the batch as its sort key, then its whole row: ``(key tuple, row tuple)``."""
    columns = [c.to_pylist() for c in batch.columns]
    rows = list(zip(*columns, strict=True))
    if not keys:
        # With no keys every row's key is the same, empty: a top-k keeps the first rows it is given.
        return [((), row) for row in rows]
    key_columns = [batch.column(k).to_pylist() for k in keys]
    return list(zip(zip(*key_columns, strict=True), rows, strict=True))


class Sort(Operator):
    """Hand the child's rows up ordered by ``keys``, each ``(column, descending)``: all of them
    held, then sorted with Python's own sort (a merge sort that finds runs already in order)."""

    def __init__(self, child: Operator, keys: list[tuple[str, bool]]) -> None:
        super().__init__("Sort", _listed(keys), [child])
        self.child = child
        self.keys = keys
        self.comparisons = Comparisons([d for _, d in keys])
        self.rows_held = 0

    def batches(self) -> Iterator[pa.RecordBatch]:
        rows = []
        for batch in self.child.batches():
            self.take(batch)
            rows.extend(_rows(batch, [c for c, _ in self.keys]))
        self.rows_held = len(rows)
        order = cmp_to_key(self.comparisons.compare)
        rows.sort(key=lambda r: order(r[0]))
        yield self.emit(_batch([r[1] for r in rows], self.schema()))

    def schema(self) -> pa.Schema:
        return self.child.schema()


class _Worst:
    """A row in the heap, which keeps the worst of the rows kept on top: the heap orders by the
    reverse of the sort."""

    __slots__ = ("key", "row", "comparisons")

    def __init__(self, key: tuple, row: tuple, comparisons: Comparisons) -> None:
        self.key, self.row, self.comparisons = key, row, comparisons

    def __lt__(self, other: _Worst) -> bool:
        return self.comparisons.compare(self.key, other.key) > 0


class TopK(Operator):
    """Hand up the first ``k`` rows of the child in the order of ``keys``, holding no more than
    ``k`` rows at a time: a heap whose top is the worst row kept, which each new row must beat."""

    def __init__(self, child: Operator, keys: list[tuple[str, bool]], k: int) -> None:
        detail = f"{_listed(keys)} LIMIT {k}"
        super().__init__("TopK", detail, [child])
        self.child = child
        self.keys = keys
        self.k = k
        self.comparisons = Comparisons([d for _, d in keys])
        self.rows_held = 0

    def batches(self) -> Iterator[pa.RecordBatch]:
        heap: list[_Worst] = []
        for batch in self.child.batches():
            self.take(batch)
            for key, row in _rows(batch, [c for c, _ in self.keys]):
                if len(heap) < self.k:
                    heapq.heappush(heap, _Worst(key, row, self.comparisons))
                elif self.comparisons.compare(key, heap[0].key) < 0:
                    heapq.heapreplace(heap, _Worst(key, row, self.comparisons))
                self.rows_held = max(self.rows_held, len(heap))
        kept = sorted(heap, key=cmp_to_key(lambda a, b: self.comparisons.compare(a.key, b.key)))
        yield self.emit(_batch([w.row for w in kept], self.schema()))

    def schema(self) -> pa.Schema:
        return self.child.schema()


def _listed(keys: list[tuple[str, bool]]) -> str:
    return ", ".join(f"{c} {'DESC' if d else 'ASC'}" for c, d in keys)


def _batch(rows: list[tuple], schema: pa.Schema) -> pa.RecordBatch:
    columns = list(zip(*rows, strict=True)) if rows else [[] for _ in schema]
    return pa.RecordBatch.from_arrays(
        [pa.array(c, type=f.type) for c, f in zip(columns, schema, strict=True)], schema=schema
    )
