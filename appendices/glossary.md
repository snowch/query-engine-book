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

**Binding.** Resolving every name a query uses to what it names: each column to the table it belongs
to, checked against the tables' schemas. [ch11](#from-sql-to-a-logical-plan)

**Branch predictor.** The part of a processor that guesses which way a branch will go, from the
way it went before, so the processor can start on the guessed path at once.
[ch06](#expressions-and-vectorised-kernels)

**Broadcast.** Sending a copy of a whole, small table to every machine, so that a join need not move
the large one. [ch15](#partitioning-and-shuffle)

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

**Conjunct.** One of the parts of a condition joined by `AND`: each must hold, so each can be tested
on its own, wherever its columns are. [ch12](#optimiser-rules)

**Constant folding.** Computing every part of an expression that depends on no column once, when the
query is planned, instead of for every row. [ch06](#expressions-and-vectorised-kernels)

**Cost model.** The rule a planner uses to turn its estimates into one number for a whole plan, so
that it can choose the plan whose number is least. [ch13](#statistics-cost-and-join-order)

**Data page.** The unit a Parquet column chunk is stored in: a run of a column's values, encoded
and compressed together. [ch04](#statistics-and-pruning)

**Dictionary page.** The page of a dictionary-encoded column chunk that holds its distinct
values, which every data page of the chunk refers to by number. [ch04](#statistics-and-pruning)

**Dynamic programming.** Finding the best plan for every set of a query's tables from the best plans
for its parts, smallest sets first, so each is found once. [ch13](#statistics-cost-and-join-order)

**Equal-depth histogram.** Bounds that split a column's values into buckets holding the same number
of values each, however the values are spread. [ch13](#statistics-cost-and-join-order)

**Expression tree.** An expression as a planner holds it: columns and constants at the leaves, and
an operator at each inner node, applied to the values of the nodes below it.
[ch06](#expressions-and-vectorised-kernels)

**External sort.** A sort of more rows than memory holds: sorted runs that fit, spilled, then
merged a fan-in at a time until one merge hands the rows up in order.
[ch10](#memory-limits-and-spilling)

**Fan-in.** The number of runs one merge reads at once; each needs a batch of memory, and fewer
passes are needed the larger it is. [ch10](#memory-limits-and-spilling)

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

**Heap.** A tree kept in an array, in which each node sorts before its children, so the first
element is always the best: the top-k keeps the worst of its rows there, to replace it cheaply.
[ch09](#sorting-and-top-k)

**Heavy hitter.** A key that holds far more than its share of the rows: a customer who placed a fifth
of the orders. [ch16](#skew)

**Hive partitioning.** Laying out a table's files in directories named for a column's value, such
as `month=2024-03`, so a reader can rule out a file from its path. [ch05](#where-work-happens)

**Independence assumption.** Guessing that knowing one condition holds tells you nothing about
another, so their selectivities multiply. [ch13](#statistics-cost-and-join-order)

**Lane.** One of the values a vector register holds side by side, each worked on by the same
instruction. [ch06](#expressions-and-vectorised-kernels)

**Linear probing.** Looking in the next slot, and the next, when a key's slot in a hash table
holds another key. [ch07](#hash-aggregation)

**Logical plan.** A query's meaning as a tree of steps, such as reading a table, joining, filtering
and grouping, each saying what it hands up and not how. [ch11](#from-sql-to-a-logical-plan)

**Memory limit.** The most memory an engine, or a query, may use; an operator that needs more must
spill or fail. [ch10](#memory-limits-and-spilling)

**Merge join.** A join of two inputs sorted by the join key, which walks both from the front
together and needs no table. [ch08](#joins)

**Misprediction.** A branch that goes the other way from the branch predictor's guess, so the work
started on the guessed path is thrown away. [ch06](#expressions-and-vectorised-kernels)

**Morsel.** A slice of a query's input one worker takes at a time; for a Parquet scan, a row group.
[ch14](#parallelism-on-one-machine)

**Offset index.** Part of a Parquet file's page index: where each page of a column chunk starts,
and the first row it holds. [ch04](#statistics-and-pruning)

**Offsets.** The buffer of a string array that says where each row's bytes start and end in its
data buffer. [ch02](#batches-in-memory)

**Open addressing.** Keeping a hash table's entries in its array of slots, rather than in lists
hanging off them. [ch07](#hash-aggregation)

**Operator.** One step of a plan: a job with one input and one output, such as a scan, a filter
or a projection. [ch01](#the-plan-is-the-map)

**Optimiser.** The part of a planner that rewrites the logical plan by rules, and chooses between
plans that give the same rows. [ch12](#optimiser-rules)

**Partial aggregate.** A group's aggregates over part of its rows, such as a count and a sum,
combined later with the other parts' into the group's aggregates over all of them.
[ch07](#hash-aggregation)

**Perfect hash aggregate.** An aggregate whose table has a slot for every possible key, found by
subtracting the smallest key: possible when the keys are whole numbers from a small, known range.
[ch07](#hash-aggregation)

**Physical plan.** The operators an engine will run for a query, and how rows flow between them.
DuckDB draws it for `EXPLAIN`. [ch01](#the-plan-is-the-map)

**Pipeline.** The operators a morsel passes through, from the scan up to the first operator that must
see all its input before it can hand anything up. [ch14](#parallelism-on-one-machine)

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

**Recursive descent.** Parsing with one function for each kind of phrase in a grammar, each calling
the functions for the phrases inside it; precedence is one function per level.
[ch11](#from-sql-to-a-logical-plan)

**Rewrite rule.** A change to a logical plan that gives the same rows for no more work, whatever the
data: moving a condition down, reading fewer columns. [ch12](#optimiser-rules)

**Row group.** A horizontal slice of a Parquet file: every column's values for a run of rows,
with statistics for each column. [ch01](#the-plan-is-the-map)

**Salt.** A small number taken from a row and added to a heavy key, so that the key's rows spread over
several machines instead of one. [ch16](#skew)

**Scan.** The operator that reads rows from storage: the only operator that reads.
[ch01](#the-plan-is-the-map)

**Selectivity.** The fraction of its input rows a predicate keeps. [ch01](#the-plan-is-the-map)

**Shuffle.** Sending every row to the machine that owns its key, by the key's hash, so that rows with
equal keys meet. [ch15](#partitioning-and-shuffle)

**SIMD.** Single instruction, multiple data: instructions that apply one operation to every lane of
a wide register at once. [ch06](#expressions-and-vectorised-kernels)

**Sorted run.** A sequence of rows already in order: part of the input a sort finds in order, or a
piece of a large sort written to disk, to be merged with the others. [ch09](#sorting-and-top-k)

**Speedup.** How many times sooner a query finishes with several workers than with one.
[ch14](#parallelism-on-one-machine)

**Spilling.** Writing what does not fit in memory to temporary storage, to read it back later: a
query finishes in less memory, and pays in bytes written and read.
[ch10](#memory-limits-and-spilling)

**Stage.** The operators between two shuffles of a distributed plan, run the same way on every
machine over that machine's rows. [ch17](#stages-and-distributed-execution)

**Syntax tree.** The parts of a query's text as a tree, as the text wrote them, before any name in it
is checked. [ch11](#from-sql-to-a-logical-plan)

**Table metadata.** A file kept beside a table's data files that lists each of them with the
smallest and largest value of every column, so a reader can rule out a file without opening it.
[ch05](#where-work-happens)

**Task.** One machine's run of a stage. [ch17](#stages-and-distributed-execution)

**Token.** One word, number, string or operator of a query's text: what a parser reads, once the
spaces and comments are dropped. [ch11](#from-sql-to-a-logical-plan)

**Top-k.** The first k rows in some order, found without sorting every row: an engine keeps the
best k seen so far and compares each new row with the worst of them. [ch09](#sorting-and-top-k)

**Validity bitmap.** One bit per value in an Arrow array, saying whether the value is present or
null. [ch02](#batches-in-memory)

**Vectorised execution.** Evaluating an operator over a batch of values per call, with a kernel,
instead of over one row per call. [ch06](#expressions-and-vectorised-kernels)
