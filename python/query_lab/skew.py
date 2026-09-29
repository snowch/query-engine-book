"""Skew: when a few keys hold many of the rows, and how to spread them (ch16).

ch15's shuffle sends every row of a key to the one node that owns it. A hash spreads the keys
evenly, but not the rows: a customer who placed a fifth of the orders sends a fifth of them to one
node, and that node is still working when the others are done. The busiest node's rows are the
measure here, as the busiest worker's work was in ch14.

**Salting** splits a heavy key's rows over several nodes. Each of its rows on the side with many
gets a salt, a small number taken from the row itself, and goes to the node its key and salt name
together. The other side's row for that key is copied to every one of those nodes, so each salted
row still meets it. Keys that are not heavy go where ch15 sends them.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

import pyarrow as pa

from .distributed import COUNTRY, Result, Rows, ipc_bytes, node_of
from .join import HashJoin


def heavy_keys(parts: list[pa.Table], key: str, nodes: int) -> set:
    """The keys with more rows than half a node's even share: counted exactly, in one pass."""
    counts = Counter(k for t in parts for k in t.column(key).to_pylist())
    share = sum(counts.values()) / nodes
    return {k for k, n in counts.items() if n > share / 2}


def send(parts: list[pa.Table], where: Callable[[pa.Table], list[list[int]]]) -> tuple[list[pa.Table], int]:
    """Every row sent to each of the nodes ``where`` names for it, and the bytes that left their
    node: ch15's shuffle, where a row may go to several nodes, or to one."""
    nodes = len(parts)
    received = [[] for _ in range(nodes)]
    sent = 0
    for here, table in enumerate(parts):
        targets = where(table)
        for there in range(nodes):
            mask = pa.array([there in t for t in targets], pa.bool_())
            piece = table.filter(mask)
            if piece.num_rows == 0:
                continue
            received[there].append(piece)
            if there != here:
                sent += ipc_bytes(piece)
    return [pa.concat_tables(r) if r else parts[0].slice(0, 0) for r in received], sent


def salted(key: str, salt: str, heavy: set, fanout: int, nodes: int):
    """Where each row of the side with many rows goes: a heavy key's row to one of ``fanout``
    nodes, chosen by its ``salt`` column; any other key's row to its own node."""

    def where(table: pa.Table) -> list[list[int]]:
        keys, salts = table.column(key).to_pylist(), table.column(salt).to_pylist()
        return [
            [(node_of(k, nodes) + s % fanout) % nodes] if k in heavy else [node_of(k, nodes)]
            for k, s in zip(keys, salts, strict=True)
        ]

    return where


def copied(key: str, heavy: set, fanout: int, nodes: int):
    """Where each row of the other side goes: a heavy key's row to all ``fanout`` of its nodes."""

    def where(table: pa.Table) -> list[list[int]]:
        return [
            [(node_of(k, nodes) + s) % nodes for s in range(fanout)] if k in heavy else [node_of(k, nodes)]
            for k in table.column(key).to_pylist()
        ]

    return where


def join_salted(orders: list[pa.Table], customers: list[pa.Table], fanout: int) -> Result:
    """Each order with its customer's country, the heaviest customers' orders salted by order id
    over ``fanout`` nodes, and those customers copied to each."""
    nodes = len(orders)
    heavy = heavy_keys(orders, "customer_id", nodes)
    o, sent_o = send(orders, salted("customer_id", "order_id", heavy, fanout, nodes))
    c, sent_c = send(customers, copied("customer_id", heavy, fanout, nodes))
    joined = [
        HashJoin(Rows(a), Rows(b), "customer_id", "customer_id", COUNTRY).run()
        for a, b in zip(o, c, strict=True)
    ]
    return Result(joined, sent_o + sent_c)


def busiest(parts: list[pa.Table]) -> int:
    """The rows on the node with the most."""
    return max(t.num_rows for t in parts)
