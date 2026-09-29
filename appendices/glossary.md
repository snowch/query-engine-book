---
title: Glossary
---

(glossary)=
# Glossary

Terms the book uses, each with the chapter that introduces it. No chapter uses a term before the
chapter that introduces it: `tests/test_book.py` checks every entry.

**Arrow IPC.** The stream format Arrow uses to move batches between processes: a schema, then
batches laid out as they are in memory. [ch05](#where-work-happens)

**Batch.** A slice of a table, a few thousand rows held column by column as Arrow arrays: what
one operator hands the next. [ch01](#the-plan-is-the-map)

**Branch predictor.** The part of a processor that guesses which way a branch will go, from the
way it went before, so the processor can start on the guessed path at once.
[ch06](#expressions-and-vectorised-kernels)

**Build side.** The input a hash join reads first and holds, in a hash table on its key, until the
join ends. [ch08](#joins)

**Cache hit.** A read whose cache line is already in the cache. [ch02](#batches-in-memory)

**Cache line.** The fixed-size block of memory a processor moves between memory and its caches.
Reading one byte brings in the whole line. [ch02](#batches-in-memory)

**Cache miss.** A read whose cache line is not in the cache, so the whole line is fetched from
memory first. [ch02](#batches-in-memory)

**Cardinality estimate.** The number of rows a planner expects an operator to produce, made
before the query runs. [ch01](#the-plan-is-the-map)

**Column index.** Part of a Parquet file's page index: the smallest and largest value of each
page of a column chunk. [ch04](#statistics-and-pruning)

**Constant folding.** Computing every part of an expression that depends on no column once, when the
query is planned, instead of for every row. [ch06](#expressions-and-vectorised-kernels)

**Data page.** The unit a Parquet column chunk is stored in: a run of a column's values, encoded
and compressed together. [ch04](#statistics-and-pruning)

**Dictionary page.** The page of a dictionary-encoded column chunk that holds its distinct
values, which every data page of the chunk refers to by number. [ch04](#statistics-and-pruning)

**Expression tree.** An expression as a planner holds it: columns and constants at the leaves, and
an operator at each inner node, applied to the values of the nodes below it.
[ch06](#expressions-and-vectorised-kernels)

**Filter.** The operator that keeps the rows for which a predicate is true.
[ch01](#the-plan-is-the-map)

**Filter pushdown.** Testing a query's predicates inside the scan, so it hands up only the rows
that pass. [ch03](#projection-and-filter-pushdown)

**Gather.** Reading rows by position, in an order given by a list of positions: row `k` of the
output is row `positions[k]` of the input. A sort, a join and a lookup each end in one.
[ch02](#batches-in-memory)

**Hash join.** A join that holds one input, the build side, in a hash table on the join key, and
streams the other, the probe side, past it, looking each row's key up. [ch08](#joins)

**Hash table.** An array of slots in which a key's hash picks the slot to look in first: how an
engine finds a row's group, or a row's match. [ch07](#hash-aggregation)

**Hive partitioning.** Laying out a table's files in directories named for a column's value, such
as `month=2024-03`, so a reader can rule out a file from its path. [ch05](#where-work-happens)

**Lane.** One of the values a vector register holds side by side, each worked on by the same
instruction. [ch06](#expressions-and-vectorised-kernels)

**Linear probing.** Looking in the next slot, and the next, when a key's slot in a hash table
holds another key. [ch07](#hash-aggregation)

**Merge join.** A join of two inputs sorted by the join key, which walks both from the front
together and needs no table. [ch08](#joins)

**Misprediction.** A branch that goes the other way from the branch predictor's guess, so the work
started on the guessed path is thrown away. [ch06](#expressions-and-vectorised-kernels)

**Offset index.** Part of a Parquet file's page index: where each page of a column chunk starts,
and the first row it holds. [ch04](#statistics-and-pruning)

**Offsets.** The buffer of a string array that says where each row's bytes start and end in its
data buffer. [ch02](#batches-in-memory)

**Open addressing.** Keeping a hash table's entries in its array of slots, rather than in lists
hanging off them. [ch07](#hash-aggregation)

**Operator.** One step of a plan: a job with one input and one output, such as a scan, a filter
or a projection. [ch01](#the-plan-is-the-map)

**Partial aggregate.** A group's aggregates over part of its rows, such as a count and a sum,
combined later with the other parts' into the group's aggregates over all of them.
[ch07](#hash-aggregation)

**Perfect hash aggregate.** An aggregate whose table has a slot for every possible key, found by
subtracting the smallest key: possible when the keys are whole numbers from a small, known range.
[ch07](#hash-aggregation)

**Physical plan.** The operators an engine will run for a query, and how rows flow between them.
DuckDB draws it for `EXPLAIN`. [ch01](#the-plan-is-the-map)

**Predicate.** A condition that each row either meets or does not, such as
`status = 'returned'`. [ch01](#the-plan-is-the-map)

**Probe side.** The input a hash join streams past its table, a batch at a time, looking each
row's key up. [ch08](#joins)

**Profile.** A plan's operators after a run, each with counters from that run.
[ch01](#the-plan-is-the-map)

**Projection.** The operator that computes the columns a query returns from the columns it is
given, and drops the rest. [ch01](#the-plan-is-the-map)

**Projection pushdown.** Reading only the columns a query uses, inside the scan, so no other
column's bytes are fetched. [ch03](#projection-and-filter-pushdown)

**Pruning.** Skipping a row group, unread, because its statistics show no row in it can satisfy
the query's predicates. [ch03](#projection-and-filter-pushdown)

**Pull model.** Running a plan by having each operator ask the one below it for a batch when it
needs one, so the top of the plan drives the run. [ch01](#the-plan-is-the-map)

**Pushdown.** Handing work to the operator that reads the data, so that data never has to leave
it. [ch03](#projection-and-filter-pushdown)

**Row group.** A horizontal slice of a Parquet file: every column's values for a run of rows,
with statistics for each column. [ch01](#the-plan-is-the-map)

**Scan.** The operator that reads rows from storage: the only operator that reads.
[ch01](#the-plan-is-the-map)

**Selectivity.** The fraction of its input rows a predicate keeps. [ch01](#the-plan-is-the-map)

**SIMD.** Single instruction, multiple data: instructions that apply one operation to every lane of
a wide register at once. [ch06](#expressions-and-vectorised-kernels)

**Table metadata.** A file kept beside a table's data files that lists each of them with the
smallest and largest value of every column, so a reader can rule out a file without opening it.
[ch05](#where-work-happens)

**Validity bitmap.** One bit per value in an Arrow array, saying whether the value is present or
null. [ch02](#batches-in-memory)

**Vectorised execution.** Evaluating an operator over a batch of values per call, with a kernel,
instead of over one row per call. [ch06](#expressions-and-vectorised-kernels)
