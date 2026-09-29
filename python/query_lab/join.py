"""Joining two inputs on a key: the hash join (ch08).

A join pairs each row of one input with the rows of the other whose key equals its own. The hash
join does it in two phases. First it reads the whole of one input, the **build side**, into a hash
table keyed on the join key: for each key, the build rows that hold it. Then it streams the other
input, the **probe side**, a batch at a time, and looks each row's key up in the table, handing up
a joined row for every build row it finds. Only the build side is held in memory, so an engine
builds on the smaller input, and the table's size, against the cache's, decides what each probe
costs.

The table is ch07's (:class:`~query_lab.aggregate.HashTable`), so it counts the same things:
lookups, probes, resizes, and, given a cache, the lines each probe reads. The build rows sit in
an area of their own, :data:`ROW_BYTES` per column per row, and every match reads its row from
there through the same cache, as a real engine's does.
"""

from __future__ import annotations

from collections.abc import Iterator

import pyarrow as pa

from .aggregate import HashTable
from .operators import Operator

#: What the model gives each held value, and each row's link to the next row with its key: eight
#: bytes, the width of a number or of a pointer to a string's bytes.
ROW_BYTES = 8


class HashJoin(Operator):
    """An inner join of ``probe`` and ``build`` on ``probe_key = build_key``, handing up the
    ``columns`` named, each as ``(side, column)`` with ``side`` either ``"probe"`` or ``"build"``.

    The children are the probe side, then the build side, as DuckDB draws them.
    """

    def __init__(
        self,
        probe: Operator,
        build: Operator,
        probe_key: str,
        build_key: str,
        columns: list[tuple[str, str]],
        table: HashTable | None = None,
    ) -> None:
        detail = f"{probe_key} = {build_key}: {', '.join(c for _, c in columns)}"
        super().__init__("HashJoin", detail, [probe, build])
        self.probe, self.build = probe, build
        self.probe_key, self.build_key = probe_key, build_key
        self.columns = columns
        self.table = table if table is not None else HashTable()
        self.build_rows = 0
        """Rows the build side handed up: every one of them is held until the join ends."""
        self.row_bytes = ROW_BYTES * (1 + sum(side == "build" for side, _ in columns))
        """What one held build row takes: each of its columns, and its link to the next row."""

    def batches(self) -> Iterator[pa.RecordBatch]:
        # Build: the whole build side into the table, each key's rows in a list of its own.
        wanted = [c for side, c in self.columns if side == "build"]
        held: dict[str, list] = {c: [] for c in wanted}
        matches: list[list[int]] = []
        for batch in self.build.batches():
            self.take(batch)
            keys = batch.column(self.build_key).to_pylist()
            values = {c: batch.column(c).to_pylist() for c in wanted}
            for i, key in enumerate(keys):
                group, new = self.table.find(key)
                if new:
                    matches.append([])
                matches[group].append(self.build_rows)
                for c in wanted:
                    held[c].append(values[c][i])
                self.build_rows += 1
        # Probe: every probe row's key looked up; a joined row for each build row it matches.
        schema = self.schema()
        for batch in self.probe.batches():
            self.take(batch)
            keys = batch.column(self.probe_key).to_pylist()
            probe_values = {c: batch.column(c).to_pylist() for side, c in self.columns if side == "probe"}
            # One list per output column, by position: a self-join names two columns alike.
            out: list[list] = [[] for _ in self.columns]
            for i, key in enumerate(keys):
                group = self.table.get(key)
                if group is None:
                    continue
                for row in matches[group]:
                    if self.table.cache is not None:
                        self.table.cache.read("build rows", row * self.row_bytes, self.row_bytes)
                    for j, (side, c) in enumerate(self.columns):
                        out[j].append(probe_values[c][i] if side == "probe" else held[c][row])
            arrays = [pa.array(values, type=field.type) for values, field in zip(out, schema, strict=True)]
            yield self.emit(pa.RecordBatch.from_arrays(arrays, schema=schema))

    @property
    def held_bytes(self) -> int:
        """The build side as the join holds it: its rows, and the table that finds them."""
        return self.build_rows * self.row_bytes + self.table.table_bytes

    def schema(self) -> pa.Schema:
        sides = {"probe": self.probe.schema(), "build": self.build.schema()}
        return pa.schema([sides[side].field(c) for side, c in self.columns])
