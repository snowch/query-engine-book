"""Stages: a distributed plan cut where rows must move, run one stage at a time (ch17).

A distributed engine cuts its plan at every shuffle. Each piece is a **stage**: the same operators
run as one **task** on every node, over that node's rows, and a stage's output is shuffled to the
next stage's tasks. Nothing in a stage waits for another node; everything between stages does.

The query here is what each country's customers spent, largest first, in four stages:

1. read each node's orders and customers, and shuffle both by customer;
2. join each node's orders and customers, aggregate by country in part, and shuffle by country;
3. finish each country's aggregate, and gather the countries on one node;
4. sort them, on that one node.

Between stages the shuffled rows must be kept somewhere until the next stage reads them. Where
they are kept decides what a failed node costs: :func:`rerun` counts the tasks a failure makes the
engine run again.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pyarrow as pa

from . import distributed as d
from .aggregate import Aggregate, HashAggregate
from .join import HashJoin
from .sort import Sort


@dataclass
class Stage:
    name: str
    tasks: int
    rows_in: int = 0
    bytes_out: int = 0
    """The bytes the stage's tasks shuffled on to the next stage."""
    feeds: list[str] = field(default_factory=list)
    """The stages whose output this one reads."""


def gather(parts: list[pa.Table]) -> tuple[list[pa.Table], int]:
    """Every node's rows sent to node 0, and the bytes of those that were elsewhere."""
    sent = sum(d.ipc_bytes(t) for t in parts[1:])
    return [pa.concat_tables(parts)] + [parts[0].slice(0, 0)] * (len(parts) - 1), sent


def spend_by_country(root: Path, nodes: int) -> tuple[pa.Table, list[Stage]]:
    """queries/spend_by_country.sql run stage by stage on ``nodes`` simulated nodes."""
    fixtures = root / "fixtures"
    orders = d.place(fixtures / "orders-sorted.parquet", ["customer_id", "amount"], nodes)
    customers = d.place(fixtures / "customers.parquet", ["customer_id", "country"], nodes)

    read = Stage("read and shuffle by customer", nodes, sum(t.num_rows for t in orders + customers))
    o, sent_o = d.shuffle(orders, "customer_id")
    c, sent_c = d.shuffle(customers, "customer_id")
    read.bytes_out = sent_o + sent_c

    join = Stage("join, aggregate in part", nodes, sum(t.num_rows for t in o + c), feeds=[read.name])
    columns = [("build", "country"), ("probe", "amount")]
    spend = [Aggregate("orders", "count"), Aggregate("spent", "sum", "amount")]
    partial = [
        HashAggregate(
            HashJoin(d.Rows(a), d.Rows(b), "customer_id", "customer_id", columns), ["country"], spend
        ).run()
        for a, b in zip(o, c, strict=True)
    ]
    by_country, join.bytes_out = d.shuffle(partial, "country")

    final = Stage("finish the aggregate", nodes, sum(t.num_rows for t in by_country), feeds=[join.name])
    sums = [Aggregate("orders", "sum", "orders"), Aggregate("spent", "sum", "spent")]
    totals = [HashAggregate(d.Rows(t), ["country"], sums).run() for t in by_country]
    gathered, final.bytes_out = gather(totals)

    last = Stage("sort", 1, gathered[0].num_rows, feeds=[final.name])
    result = Sort(d.Rows(gathered[0]), [("spent", True)]).run()
    return result, [read, join, final, last]


#: Where a stage's shuffled output is kept until the next stage reads it.
KEPT = {
    "nowhere": "passed straight on, kept by no one",
    "on the node": "on the disk of the node that wrote it",
    "in shared storage": "in storage every node can read",
}


def rerun(stages: list[Stage], failed: int, kept: str) -> int:
    """The tasks run again when one node dies during the stage at index ``failed``.

    Passed straight on, nothing survives: every task that has run so far runs again, the query
    from the start. Kept on the node that wrote it, what the dead node wrote is lost with it: its
    task in each stage so far runs again. Kept in shared storage, every earlier stage's output
    survives, and only the dead node's task in the failed stage runs again.
    """
    match kept:
        case "nowhere":
            return sum(s.tasks for s in stages[: failed + 1])
        case "on the node":
            return failed + 1
        case "in shared storage":
            return 1
    raise ValueError(f"kept must be one of {', '.join(KEPT)}")
