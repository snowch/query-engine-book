"""Pushing instead of pulling (ch18).

Every operator so far pulled: it asked the operator below it for a batch when it wanted one, and
the operator at the top drove the run. DuckDB runs the other way round. The source of a pipeline
loops over its input and **pushes** each batch into the operator above it, which does its work
and pushes the result on, until the batch reaches a **sink**: an operator that keeps what it is
given, such as an aggregate's table or the query's result. The work is the same; what changes is
who holds the loop.

Two things follow, and this module counts both. Only the source's loop can stop a pushed
pipeline, so an operator that has seen enough must say so, and the source must listen. And a
source that pushes can hand the same batch to two operators, so two consumers of one input can
share one scan, where two pulled plans would each need their own.

Each step keeps the same counters as a pulled operator, and they obey COUNTERS.md's invariants: a
step's rows in are the rows its input handed it.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc

from .aggregate import Aggregate, HashAggregate, HashTable, _finish, _start, _step
from .metrics import Metrics
from .operators import BatchFunction, Comparison, Operator, Scan


class Step:
    """One operator of a pushed pipeline. It is handed a batch, does its work on it, and pushes
    the result on to the steps after it. Its answer says whether anything after it wants more."""

    def __init__(self, name: str, detail: str, then: list[Step]) -> None:
        self.metrics = Metrics(name, detail)
        self.then = then
        # The counters read as a pulled plan's do: each step after this one takes its rows from it.
        for step in then:
            step.metrics.children.append(self.metrics)

    def push(self, batch: pa.RecordBatch) -> bool:
        raise NotImplementedError

    def finish(self) -> None:
        """The source has nothing more: pass the word on, so every sink can finish its work."""
        for step in self.then:
            step.finish()

    def take(self, batch: pa.RecordBatch) -> pa.RecordBatch:
        self.metrics.rows_in += batch.num_rows
        self.metrics.batches_in += 1
        return batch

    def emit(self, batch: pa.RecordBatch) -> pa.RecordBatch:
        self.metrics.rows_out += batch.num_rows
        self.metrics.batches_out += 1
        self.metrics.peak_memory_bytes = max(self.metrics.peak_memory_bytes, batch.get_total_buffer_size())
        return batch


def drive(source: Operator, step: Step, listen: bool = True) -> None:
    """Run a pipeline: the source's loop pushes each of its batches into ``step``. A source that
    listens stops as soon as nothing downstream wants more; one that does not reads to the end."""
    step.metrics.children.append(source.metrics)
    for batch in source.batches():
        wants_more = step.push(batch)
        if listen and not wants_more:
            break
    step.finish()


class Filter(Step):
    """Keep the rows of each batch for which ``predicate`` is true, and push them on."""

    def __init__(self, description: str, predicate: BatchFunction, then: Step) -> None:
        super().__init__("Filter", description, [then])
        self.predicate = predicate

    def push(self, batch: pa.RecordBatch) -> bool:
        self.take(batch)
        return self.then[0].push(self.emit(batch.filter(self.predicate(batch))))


class Tee(Step):
    """One input pushed to several steps: every batch goes to each of them. It wants more while
    any of them does."""

    def __init__(self, then: list[Step]) -> None:
        super().__init__("Tee", f"{len(then)} consumers", then)

    def push(self, batch: pa.RecordBatch) -> bool:
        self.emit(self.take(batch))
        answers = [step.push(batch) for step in self.then]
        return any(answers)


class Exists(Step):
    """A sink that answers whether any row reached it. The first row answers the question, so from
    then on it wants no more."""

    def __init__(self) -> None:
        super().__init__("Exists", "", [])
        self.found = False

    def push(self, batch: pa.RecordBatch) -> bool:
        self.take(batch)
        self.found = self.found or batch.num_rows > 0
        return not self.found

    def finish(self) -> None:
        self.emit(pa.record_batch({"exists": [self.found]}))


class Group(Step):
    """ch07's hash aggregate as a sink: each batch pushed in moves its rows' groups on, and the
    groups are ready only once the source has finished. It wants every row there is."""

    def __init__(self, keys: list[str], aggregates: list[Aggregate], schema: pa.Schema) -> None:
        super().__init__("Group", f"{', '.join(keys)}: {', '.join(map(str, aggregates))}", [])
        self.keys, self.aggregates, self.input = keys, aggregates, schema
        self.table, self.states = HashTable(), []
        self.result: pa.RecordBatch | None = None

    def push(self, batch: pa.RecordBatch) -> bool:
        self.take(batch)
        keys = [batch.column(k).to_pylist() for k in self.keys]
        values = [batch.column(a.column).to_pylist() if a.column else None for a in self.aggregates]
        for i in range(batch.num_rows):
            group, new = self.table.find(tuple(k[i] for k in keys))
            if new:
                self.states.append([_start(a) for a in self.aggregates])
            for j, a in enumerate(self.aggregates):
                self.states[group][j] = _step(
                    a.func, self.states[group][j], values[j][i] if values[j] is not None else 1
                )
        return True

    def finish(self) -> None:
        schema = HashAggregate(Source([], self.input), self.keys, self.aggregates).schema()
        columns = [[key[k] for key in self.table.keys] for k in range(len(self.keys))]
        columns += [[_finish(a.func, s[j]) for s in self.states] for j, a in enumerate(self.aggregates)]
        arrays = [pa.array(c, type=f.type) for c, f in zip(columns, schema, strict=True)]
        self.result = self.emit(pa.RecordBatch.from_arrays(arrays, schema=schema))


class Collect(Step):
    """The query's result: a sink that keeps every batch pushed to it."""

    def __init__(self) -> None:
        super().__init__("Collect", "", [])
        self.batches: list[pa.RecordBatch] = []

    def push(self, batch: pa.RecordBatch) -> bool:
        self.batches.append(self.emit(self.take(batch)))
        return True


class Source(Operator):
    """Batches left in a sink by one pipeline, handed out again as the source of the next."""

    def __init__(self, batches: list[pa.RecordBatch], schema: pa.Schema) -> None:
        super().__init__("Source", "a sink's result", [])
        self.held, self.shape = batches, schema

    def batches(self):
        for batch in self.held:
            yield self.emit(batch)

    def schema(self) -> pa.Schema:
        return self.shape


# ch18's two queries, pushed. Each returns its sinks, whose counters the chapter reads.

ORDERS = Path("fixtures") / "orders-sorted.parquet"
RETURNED = Comparison("status", "=", "returned")


def any_returned(root: Path, listen: bool = True) -> tuple[Scan, Exists]:
    """queries/any_returned.sql: a scan that tests the status, pushing to a sink that wants one row."""
    scan = Scan(root / ORDERS, ["status"], filters=[RETURNED])
    found = Exists()
    drive(scan, found, listen)
    return scan, found


#: A consumer of the returned orders: the keys it groups them by, and what it computes of each group.
Consumer = tuple[list[str], list[Aggregate]]

#: What ch18's second query asks of the returned orders: each customer's total, and the average.
TOTALS = (["customer_id"], [Aggregate("returned", "sum", "amount")])
AVERAGE = ([], [Aggregate("average", "avg", "amount")])


def big_returners(
    root: Path, consumers: tuple[Consumer, ...] = (TOTALS, AVERAGE)
) -> tuple[list[Scan], list[Group]]:
    """queries/big_returners.sql pushed: one scan of the returned orders, and a tee that pushes
    every batch to each consumer's aggregate."""
    scan = Scan(root / ORDERS, ["customer_id", "amount"], filters=[RETURNED])
    groups = [Group(keys, aggregates, scan.schema()) for keys, aggregates in consumers]
    drive(scan, Tee(groups))
    return [scan], groups


def big_returners_pulled(
    root: Path, consumers: tuple[Consumer, ...] = (TOTALS, AVERAGE)
) -> tuple[list[Scan], list[pa.Table]]:
    """The same aggregates pulled: each consumer asks its own scan for the rows it needs."""
    scans = [Scan(root / ORDERS, ["customer_id", "amount"], filters=[RETURNED]) for _ in consumers]
    tops = [HashAggregate(scan, k, a) for scan, (k, a) in zip(scans, consumers, strict=True)]
    return scans, [top.run() for top in tops]


def over_average(totals: pa.RecordBatch, average: float) -> pa.Table:
    """The second pipeline: its source is the totals the first one left in a sink, and it keeps the
    customers whose returns add up to more than the average returned order."""
    result = Collect()
    keep = Filter("returned > average", lambda b: pc.greater(b["returned"], average), result)
    drive(Source([totals], totals.schema), keep)
    return pa.Table.from_batches(result.batches, schema=totals.schema).sort_by("customer_id")


def result_of(groups: list[Group]) -> pa.Table:
    """ch18's answer from the two aggregates the first pipeline filled."""
    totals, average = groups[0].result, groups[1].result.column("average")[0].as_py()
    return over_average(totals, average)
