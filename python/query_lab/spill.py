"""Sorting more rows than memory holds: runs written to temporary storage, then merged (ch10).

A sort with a memory limit fills its memory with rows, sorts them into a **sorted run**, and
writes the run to temporary storage, which frees the memory for the next. Writing what does not
fit, to read it back later, is **spilling**. Once every row is in a run, the runs are merged, a
few at a time: the number of runs one merge reads at once is its **fan-in**, and each needs a
batch of memory. With more runs than the fan-in, one pass of merging leaves fewer, longer runs,
which are spilled again, and merged again, until one pass can merge them all and hand the rows
up in order. Sorting this way is an **external sort**.

The operator counts what it wrote to temporary storage and what it read back, as Arrow IPC,
the format the engine spills in (COUNTERS.md), and how many runs and passes it made.
"""

from __future__ import annotations

import heapq
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cmp_to_key

import pyarrow as pa

from .operators import Operator
from .sort import Comparisons, _batch, _listed, _rows

#: The rows in each batch a run is written in, and read back in: a merge holds one batch of each
#: run it reads.
RUN_BATCH_ROWS = 256


@dataclass
class TempStore:
    """Temporary storage: files of bytes by name, counting what was written and read."""

    written: int = 0
    read: int = 0
    files: dict[str, bytes] = field(default_factory=dict, repr=False)

    def write(self, name: str, data: bytes) -> None:
        self.files[name] = data
        self.written += len(data)

    def open(self, name: str) -> bytes:
        data = self.files.pop(name)
        self.read += len(data)
        return data


class ExternalSort(Operator):
    """Hand the child's rows up ordered by ``keys``, holding no more than ``memory_limit`` bytes of
    rows at a time, and merging at most ``fan_in`` runs at once."""

    def __init__(
        self,
        child: Operator,
        keys: list[tuple[str, bool]],
        memory_limit: int,
        fan_in: int = 8,
        temp: TempStore | None = None,
    ) -> None:
        super().__init__("ExternalSort", f"{_listed(keys)}; {memory_limit:,} bytes, fan-in {fan_in}", [child])
        if fan_in < 2:
            raise ValueError("a merge reads at least two runs")
        self.child = child
        self.keys = keys
        self.memory_limit = memory_limit
        self.fan_in = fan_in
        self.temp = temp if temp is not None else TempStore()
        self.order = _order_key(keys)
        self.sorted_runs = 0
        """Runs cut from the input, sorted and spilled."""
        self.run_rows: list[int] = []
        """The rows in each of those runs, in order."""
        self.merged_runs = 0
        """Runs a merge pass wrote, before the last pass, which writes nothing."""
        self.passes = 0
        """Merge passes, the last one, which hands up, included. None if nothing was spilled."""
        self.rows_spilled = 0
        """Rows written to temporary storage, counted again each time a row is written."""

    def batches(self) -> Iterator[pa.RecordBatch]:
        # Fill memory, sort, spill: one run each time the next batch would not fit.
        held: list[pa.RecordBatch] = []
        held_bytes = 0
        runs: list[str] = []
        for batch in self.child.batches():
            self.take(batch)
            size = batch.get_total_buffer_size()
            if held and held_bytes + size > self.memory_limit:
                runs.append(self._spill(self._sorted(held), merged=False))
                held, held_bytes = [], 0
            held.append(batch)
            held_bytes += size
            self.metrics.peak_memory_bytes = max(self.metrics.peak_memory_bytes, held_bytes)
        if not runs:
            # Everything fitted: an in-memory sort, and nothing written.
            yield self.emit(_batch(self._sorted(held), self.schema()))
            return
        runs.append(self._spill(self._sorted(held), merged=False))
        # Merge fan_in runs at a time, spilling what each pass makes, until one pass is enough.
        while len(runs) > self.fan_in:
            self.passes += 1
            runs = [
                self._spill(list(self._merged(runs[i : i + self.fan_in])), merged=True)
                for i in range(0, len(runs), self.fan_in)
            ]
        self.passes += 1
        rows = list(self._merged(runs))
        for start in range(0, len(rows), RUN_BATCH_ROWS):
            yield self.emit(_batch(rows[start : start + RUN_BATCH_ROWS], self.schema()))

    def _sorted(self, batches: list[pa.RecordBatch]) -> list[tuple]:
        keyed = [r for b in batches for r in _rows(b, [c for c, _ in self.keys])]
        keyed.sort(key=lambda r: self.order(r[0]))
        return [row for _, row in keyed]

    def _spill(self, rows: list[tuple], merged: bool) -> str:
        """Write sorted rows to temporary storage as one run, in batches, and name it."""
        name = f"run {self.sorted_runs + self.merged_runs}"
        if merged:
            self.merged_runs += 1
        else:
            self.sorted_runs += 1
            self.run_rows.append(len(rows))
        schema = self.schema()
        sink = pa.BufferOutputStream()
        with pa.ipc.new_stream(sink, schema) as writer:
            for start in range(0, len(rows), RUN_BATCH_ROWS):
                writer.write_batch(_batch(rows[start : start + RUN_BATCH_ROWS], schema))
        self.temp.write(name, sink.getvalue().to_pybytes())
        self.rows_spilled += len(rows)
        return name

    def _merged(self, runs: list[str]) -> Iterator[tuple]:
        """The rows of ``runs`` in order, each run read back a batch at a time."""
        columns = [c for c, _ in self.keys]

        def rows_of(name: str) -> Iterator[tuple]:
            for batch in pa.ipc.open_stream(self.temp.open(name)):
                yield from _rows(batch, columns)

        for _, row in heapq.merge(*(rows_of(r) for r in runs), key=lambda r: self.order(r[0])):
            yield row

    def schema(self) -> pa.Schema:
        return self.child.schema()


def _order_key(keys: list[tuple[str, bool]]):
    """A function from a row's sort key to something Python orders as the ``ORDER BY`` does. This
    operator counts bytes, not comparisons, so it sorts with plain tuples, the fastest way Python
    has: a descending number is negated. Any other descending key falls back to ch09's counted
    comparison."""
    descending = [d for _, d in keys]
    fallback = cmp_to_key(Comparisons(descending).compare)

    def key(values: tuple):
        try:
            return tuple(-v if d else v for v, d in zip(values, descending, strict=True))
        except TypeError:
            return (fallback(values),)

    return key
