"""Parallelism on one machine, simulated in counters (ch14).

The book's DuckDB runs one thread, in the page and at a desk, and the book never prints a time.
So this chapter does not time threads: it counts what each would do. A plan's scan is split into
**morsels**, one per row group, and a pipeline of operators runs on each morsel separately. Each
simulated worker takes the next morsel as soon as it is free. The work of a morsel is the rows its
operators take in, the counter every operator already keeps.

What cannot be split waits for every worker to finish: an aggregate's workers each fill a table
of their own, and one worker then combines the tables. The query is done when the busiest worker
is, and the combining after it. :func:`speedup` is the work on one worker divided by that.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .operators import Operator


class Morsel(Operator):
    """One row group of a file, handed to a pipeline as its only batch."""

    def __init__(self, path: Path, index: int, columns: list[str]) -> None:
        super().__init__("Morsel", f"{path.name}, row group {index}", [])
        self.path, self.index, self.columns = path, index, columns

    def batches(self):
        table = pq.ParquetFile(self.path).read_row_group(self.index, columns=self.columns)
        for batch in table.to_batches(max_chunksize=table.num_rows or None):
            yield self.emit(batch)

    def schema(self) -> pa.Schema:
        return pq.read_schema(self.path).empty_table().select(self.columns).schema


@dataclass
class Run:
    """What a parallel run counted: each morsel's work, each worker's, and the work left after."""

    morsels: list[int]
    workers: list[int]
    after: int
    """Work that waits for every worker: combining their partial results."""

    @property
    def total(self) -> int:
        """The work on one worker, which has nothing to combine."""
        return sum(self.morsels)

    @property
    def finished(self) -> int:
        """When the query is done: the busiest worker's work, then the work that waited for it."""
        return max(self.workers) + self.after

    @property
    def speedup(self) -> float:
        return self.total / self.finished if self.finished else 1.0


#: The pipelines ch14 runs in parallel, by name: the columns each reads, the operators it runs on
#: a morsel, and the keys it groups by, if it ends in an aggregate.
def returned_orders(morsel: Operator) -> Operator:
    """ch01's query as a pipeline: two filters and a projection, on one morsel."""
    import pyarrow.compute as pc

    from .operators import Filter, Project
    from .plans import unit_price

    returned = Filter(morsel, "status = 'returned'", lambda b: pc.equal(b["status"], "returned"))
    pricey = Filter(returned, "amount / quantity > 100", lambda b: pc.greater(unit_price(b), 100))
    return Project(pricey, {"order_id": lambda b: b["order_id"], "unit_price": unit_price})


def orders_per_customer(morsel: Operator) -> Operator:
    """ch07's query as a pipeline: one worker's share of the aggregate, on one morsel."""
    from .aggregate import HashAggregate
    from .plans import ORDERS_AND_SPEND

    return HashAggregate(morsel, ["customer_id"], ORDERS_AND_SPEND)


RETURNED = (["order_id", "status", "amount", "quantity"], returned_orders, None)
PER_CUSTOMER = (["customer_id", "amount"], orders_per_customer, ["customer_id"])


def assign(work: list[int], workers: int) -> list[int]:
    """The worker each morsel goes to, taken in order, each by the worker whose work so far is
    least: the one free soonest."""
    loads, owner = [0] * workers, []
    for w in work:
        i = loads.index(min(loads))
        owner.append(i)
        loads[i] += w
    return owner


def work_of(operator: Operator) -> int:
    """The work a pipeline did: the rows each of its operators took in, and the rows its scan
    handed up, added together."""
    walk = list(operator.metrics.walk())
    return sum(m.rows_in for m in walk) + sum(m.rows_out for m in walk if not m.children)


def run(
    path: Path,
    columns: list[str],
    pipeline: Callable[[Operator], Operator],
    workers: int,
    group_keys: list[str] | None = None,
) -> Run:
    """``pipeline`` run on every row group of ``path`` by ``workers`` simulated workers. With
    ``group_keys``, the pipeline ends in an aggregate: each worker keeps one table of groups for
    all its morsels, and one worker combines the tables once every worker is done."""
    count = pq.ParquetFile(path).metadata.num_row_groups
    ops = [pipeline(Morsel(path, i, columns)) for i in range(count)]
    outputs = [op.run() for op in ops]
    work = [work_of(op) for op in ops]
    owner = assign(work, workers)
    loads = [sum(w for w, o in zip(work, owner, strict=True) if o == k) for k in range(workers)]
    after = 0
    # One worker has one table, and nothing to combine.
    for k in range(workers if group_keys and workers > 1 else 0):
        # The combining takes in one row for every group in every worker's table.
        groups = set()
        for i in (i for i in range(count) if owner[i] == k):
            groups |= set(zip(*(outputs[i].column(c).to_pylist() for c in group_keys), strict=True))
        after += len(groups)
    return Run(work, loads, after)
