"""Partitioning and shuffle, simulated on one machine (ch15).

A table too large for one machine is spread over several, each holding a part of its rows: a
**partition**. The simulated cluster here is a list of Arrow tables, one per node. Nothing moves
between nodes except through :func:`shuffle` and :func:`broadcast`, and both count what they send
as ``bytes_shuffled``: the Arrow IPC bytes of the rows that leave the node they were on, as
COUNTERS.md defines it. A row that stays where it is costs nothing.

- :func:`place` spreads a file's row groups over the nodes, one after another, as a distributed
  engine spreads a table's files.
- :func:`shuffle` sends every row to the node its key's hash names, so that equal keys meet.
- :func:`broadcast` sends a copy of a whole table to every node.

The plans on top, an aggregate and a join each done two ways, run the engine's own operators on
each node's rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .aggregate import Aggregate, HashAggregate, hash_key
from .join import HashJoin
from .operators import Operator


class Rows(Operator):
    """A node's rows, handed to the engine's operators as one batch."""

    def __init__(self, table: pa.Table) -> None:
        super().__init__("Rows", f"{table.num_rows} rows", [])
        self.table = table

    def batches(self):
        for batch in self.table.combine_chunks().to_batches():
            yield self.emit(batch)

    def schema(self) -> pa.Schema:
        return self.table.schema


def ipc_bytes(table: pa.Table) -> int:
    """The bytes ``table`` takes as an Arrow IPC stream: what sending it would send."""
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().size


def place(path: Path, columns: list[str], nodes: int) -> list[pa.Table]:
    """Each node's part of a file: its row groups dealt out to the nodes in turn."""
    f = pq.ParquetFile(path)
    parts = [[] for _ in range(nodes)]
    for i in range(f.metadata.num_row_groups):
        parts[i % nodes].append(f.read_row_group(i, columns=columns))
    empty = f.schema_arrow.empty_table().select(columns)
    return [pa.concat_tables(p) if p else empty for p in parts]


def node_of(key: object, nodes: int) -> int:
    """The node a key belongs to: its hash, the same on every node, modulo the nodes."""
    return hash_key(key) % nodes


def shuffle(parts: list[pa.Table], key: str) -> tuple[list[pa.Table], int]:
    """Every row sent to the node its ``key`` belongs to, and the bytes that left their node."""
    nodes = len(parts)
    received = [[] for _ in range(nodes)]
    sent = 0
    for here, table in enumerate(parts):
        owners = pa.array([node_of(k, nodes) for k in table.column(key).to_pylist()], pa.int64())
        for there in range(nodes):
            piece = table.filter(pa.compute.equal(owners, there))
            if piece.num_rows == 0:
                continue
            received[there].append(piece)
            if there != here:
                sent += ipc_bytes(piece)
    return [pa.concat_tables(r) if r else parts[0].slice(0, 0) for r in received], sent


def broadcast(table: pa.Table, nodes: int) -> tuple[list[pa.Table], int]:
    """A copy of ``table``, held by one node, on every node, and the bytes of the copies sent."""
    return [table] * nodes, ipc_bytes(table) * (nodes - 1)


# Two ways to aggregate, and two ways to join. ---------------------------------------------------


@dataclass
class Result:
    parts: list[pa.Table]
    """Each node's part of the result."""
    shuffled: int
    """The bytes sent between nodes."""

    def table(self) -> pa.Table:
        return pa.concat_tables(self.parts)


SPEND = [Aggregate("orders", "count"), Aggregate("spent", "sum", "amount")]


def aggregate_after_shuffle(orders: list[pa.Table], key: str = "customer_id") -> Result:
    """Orders and spend per ``key``: every order sent to its key's node, then aggregated there."""
    parts, sent = shuffle(orders, key)
    return Result([HashAggregate(Rows(p), [key], SPEND).run() for p in parts], sent)


def aggregate_in_two_phases(orders: list[pa.Table], key: str = "customer_id") -> Result:
    """The same, with each node aggregating its own orders first: only those partial aggregates
    are sent, and each key's partials are added together on its node."""
    partial = [HashAggregate(Rows(p), [key], SPEND).run() for p in orders]
    parts, sent = shuffle(partial, key)
    final = [Aggregate("orders", "sum", "orders"), Aggregate("spent", "sum", "spent")]
    return Result([HashAggregate(Rows(p), [key], final).run() for p in parts], sent)


COUNTRY = [("probe", "order_id"), ("build", "country")]


def join_by_shuffle(orders: list[pa.Table], customers: list[pa.Table]) -> Result:
    """Each order with its customer's country: both sides sent by customer, joined on each node."""
    o, sent_o = shuffle(orders, "customer_id")
    c, sent_c = shuffle(customers, "customer_id")
    joined = [
        HashJoin(Rows(a), Rows(b), "customer_id", "customer_id", COUNTRY).run()
        for a, b in zip(o, c, strict=True)
    ]
    return Result(joined, sent_o + sent_c)


def join_by_broadcast(orders: list[pa.Table], customers: pa.Table) -> Result:
    """The same join with the orders left where they are: every node gets all the customers."""
    copies, sent = broadcast(customers, len(orders))
    joined = [
        HashJoin(Rows(a), Rows(b), "customer_id", "customer_id", COUNTRY).run()
        for a, b in zip(orders, copies, strict=True)
    ]
    return Result(joined, sent)
