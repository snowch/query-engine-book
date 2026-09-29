"""Grouping rows by a key: a hash table, and the aggregate operator built on it (ch07).

``GROUP BY`` asks, for every row, which group it belongs to. An engine answers with a hash
table: it hashes the row's key to a slot, and looks there for the key's group. Two keys can hash
to the same slot, so the table's slots are probed one after another until the key or an empty
slot turns up. The table here uses **open addressing** with linear probing, as DuckDB's does:
the groups live in one array of slots, and a key that finds its slot taken tries the next one.
When three quarters of the slots are full the table doubles, and every group moves.

The table counts, it does not time: how many lookups, how many slots they probed, how many times
the table grew, and, through the cache model of :mod:`query_lab.cache`, which lines of the slot
array each probe touched. COUNTERS.md, *The simulators' counters*, defines them.

When a key is a whole number from a small, known range, there is a cheaper table: an array with a
slot for every value in the range, indexed by the value less the smallest. There is nothing to
hash and nothing to probe. DuckDB calls it a perfect hash aggregate, and uses it when a column's
statistics give the range.
"""

from __future__ import annotations

import datetime as dt
import struct
from collections.abc import Iterator
from dataclasses import dataclass, field

import pyarrow as pa

from .cache import Cache
from .operators import Operator

#: Each slot holds the key's hash and the number of its group: eight bytes each.
SLOT_BYTES = 16
#: The share of slots a table fills before it doubles.
LOAD = 0.75
MASK64 = (1 << 64) - 1


def mix(h: int) -> int:
    """Scramble 64 bits so that keys differing in a few bits land far apart: MurmurHash3's
    finaliser."""
    h ^= h >> 33
    h = (h * 0xFF51AFD7ED558CCD) & MASK64
    h ^= h >> 33
    h = (h * 0xC4CEB9FE1A85EC53) & MASK64
    return h ^ (h >> 33)


def hash_key(key: object) -> int:
    """A key's hash, the same in every process and in the browser. Python's own ``hash`` of a
    string changes from run to run, so the book hashes bytes itself."""
    match key:
        case bool():
            return mix(int(key))
        case int():
            return mix(key & MASK64)
        case float():
            return mix(struct.unpack("<Q", struct.pack("<d", key))[0])
        case str():
            # FNV-1a over the string's UTF-8 bytes, then mixed.
            h = 0xCBF29CE484222325
            for b in key.encode():
                h = ((h ^ b) * 0x100000001B3) & MASK64
            return mix(h)
        case dt.date():
            return mix(key.toordinal())
        case None:
            return mix(0x9E3779B97F4A7C15)
        case tuple():
            h = 0
            for part in key:
                h = mix(h ^ hash_key(part))
            return h
    raise TypeError(f"cannot hash {key!r}")


@dataclass
class HashTable:
    """Open addressing with linear probing: each key's group number, found by probing slots."""

    capacity: int = 16
    cache: Cache | None = None
    name: str = "slots"
    """The table's name in the cache model: two tables are two buffers."""
    lookups: int = 0
    """Keys looked up: one per row."""
    probes: int = 0
    """Slots looked at. A lookup that finds its key, or an empty slot, first time probes one."""
    resizes: int = 0
    """Times the table doubled."""
    keys: list = field(default_factory=list, repr=False)
    """Each group's key, by group number."""
    slots: list[int] = field(default_factory=list, repr=False)
    """Each slot's group number, or -1 for an empty slot."""
    hashes: list[int] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self.slots = [-1] * self.capacity

    def find(self, key: object) -> tuple[int, bool]:
        """The group number of ``key``, and whether this lookup created the group."""
        h = hash_key(key)
        self.lookups += 1
        mask = self.capacity - 1
        i = h & mask
        while True:
            self.probes += 1
            if self.cache is not None:
                # The slot array is a new buffer each time the table grows.
                self.cache.read(f"{self.name} {self.resizes}", i * SLOT_BYTES, SLOT_BYTES)
            group = self.slots[i]
            if group == -1:
                group = len(self.keys)
                self.keys.append(key)
                self.hashes.append(h)
                self.slots[i] = group
                if len(self.keys) > self.capacity * LOAD:
                    self._grow()
                return group, True
            if self.hashes[group] == h and self.keys[group] == key:
                return group, False
            i = (i + 1) & mask

    def _grow(self) -> None:
        """Double the slots and put every group back, in its new slot."""
        self.capacity *= 2
        self.resizes += 1
        mask = self.capacity - 1
        self.slots = [-1] * self.capacity
        for group, h in enumerate(self.hashes):
            i = h & mask
            while self.slots[i] != -1:
                i = (i + 1) & mask
            self.slots[i] = group

    @property
    def table_bytes(self) -> int:
        return self.capacity * SLOT_BYTES

    def counters(self) -> dict[str, int]:
        return {
            "groups": len(self.keys),
            "lookups": self.lookups,
            "probes": self.probes,
            "resizes": self.resizes,
            "table_bytes": self.table_bytes,
        }


@dataclass
class PerfectTable:
    """A slot for every whole number from ``low`` to ``high``: the group is found by subtracting,
    with no hash and no probe."""

    low: int
    high: int
    cache: Cache | None = None
    lookups: int = 0
    probes: int = 0
    resizes: int = 0
    keys: list = field(default_factory=list, repr=False)
    slots: list[int] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self.slots = [-1] * (self.high - self.low + 1)

    def find(self, key: int) -> tuple[int, bool]:
        self.lookups += 1
        self.probes += 1
        i = key - self.low
        if self.cache is not None:
            self.cache.read("slots", i * SLOT_BYTES, SLOT_BYTES)
        if self.slots[i] == -1:
            self.slots[i] = len(self.keys)
            self.keys.append(key)
            return self.slots[i], True
        return self.slots[i], False

    @property
    def capacity(self) -> int:
        return len(self.slots)

    @property
    def table_bytes(self) -> int:
        return self.capacity * SLOT_BYTES

    def counters(self) -> dict[str, int]:
        return {
            "groups": len(self.keys),
            "lookups": self.lookups,
            "probes": self.probes,
            "resizes": 0,
            "table_bytes": self.table_bytes,
        }


@dataclass(frozen=True)
class Aggregate:
    """One aggregate of a group: ``count``, ``sum``, ``min``, ``max`` or ``avg`` of a column, or
    ``count`` of rows when ``column`` is None."""

    name: str
    func: str
    column: str | None = None

    def __str__(self) -> str:
        return f"{self.func}({self.column or '*'})"


class HashAggregate(Operator):
    """Group the child's rows by ``keys`` and compute ``aggregates`` for each group.

    Every row is looked up in the table, a row at a time, and its group's running state updated:
    a count, a sum, a minimum, a maximum. Nothing can be handed up until the last row is in,
    since any row might belong to any group, so the operator holds every group until its child
    is done, then hands up one batch of groups, in the order they were first seen.
    """

    def __init__(
        self,
        child: Operator,
        keys: list[str],
        aggregates: list[Aggregate],
        table: HashTable | PerfectTable | None = None,
    ) -> None:
        detail = f"{', '.join(keys)}: {', '.join(map(str, aggregates))}"
        name = "PerfectHashAggregate" if isinstance(table, PerfectTable) else "HashAggregate"
        super().__init__(name, detail, [child])
        self.child = child
        self.keys = keys
        self.aggregates = aggregates
        self.table = table if table is not None else HashTable()

    def batches(self) -> Iterator[pa.RecordBatch]:
        states: list[list] = []
        for batch in self.child.batches():
            self.take(batch)
            keys = [batch.column(k).to_pylist() for k in self.keys]
            values = [batch.column(a.column).to_pylist() if a.column else None for a in self.aggregates]
            for i in range(batch.num_rows):
                key = keys[0][i] if len(keys) == 1 else tuple(k[i] for k in keys)
                group, new = self.table.find(key)
                if new:
                    states.append([_start(a) for a in self.aggregates])
                state = states[group]
                for j, a in enumerate(self.aggregates):
                    state[j] = _step(a.func, state[j], values[j][i] if values[j] is not None else 1)
        yield self.emit(self._result(states))

    def _result(self, states: list[list]) -> pa.RecordBatch:
        schema = self.schema()
        keys = self.table.keys
        columns = []
        for k, _ in enumerate(self.keys):
            columns.append([key if len(self.keys) == 1 else key[k] for key in keys])
        for j, a in enumerate(self.aggregates):
            columns.append([_finish(a.func, s[j]) for s in states])
        return pa.RecordBatch.from_arrays(
            [pa.array(c, type=f.type) for c, f in zip(columns, schema, strict=True)], schema=schema
        )

    def schema(self) -> pa.Schema:
        child = self.child.schema()
        fields = [child.field(k) for k in self.keys]
        for a in self.aggregates:
            match a.func:
                case "count":
                    fields.append(pa.field(a.name, pa.int64()))
                case "avg":
                    fields.append(pa.field(a.name, pa.float64()))
                case "sum":
                    source = child.field(a.column).type
                    fields.append(
                        pa.field(a.name, pa.float64() if pa.types.is_floating(source) else pa.int64())
                    )
                case _:
                    fields.append(pa.field(a.name, child.field(a.column).type))
        return pa.schema(fields)


# A group's running state for each aggregate, and how a row moves it on. An average keeps its
# sum and its count, and divides only at the end.


def _start(a: Aggregate):
    return [0, 0] if a.func == "avg" else (0 if a.func in ("count", "sum") else None)


def _step(func: str, state, value):
    match func:
        case "count":
            return state + (value is not None)
        case "sum":
            return state + value if value is not None else state
        case "min":
            return value if state is None or (value is not None and value < state) else state
        case "max":
            return value if state is None or (value is not None and value > state) else state
        case "avg":
            if value is not None:
                state[0] += value
                state[1] += 1
            return state
    raise ValueError(f"no aggregate {func!r}")


def _finish(func: str, state):
    if func == "avg":
        return state[0] / state[1] if state[1] else None
    return state
