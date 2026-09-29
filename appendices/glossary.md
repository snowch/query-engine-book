---
title: Glossary
---

(glossary)=
# Glossary

Terms the book uses, each with the chapter that introduces it. No chapter uses a term before the
chapter that introduces it: `tests/test_book.py` checks every entry.

**Batch.** A slice of a table, a few thousand rows held column by column as Arrow arrays: what
one operator hands the next. [ch01](#the-plan-is-the-map)

**Cache hit.** A read whose cache line is already in the cache. [ch02](#batches-in-memory)

**Cache line.** The fixed-size block of memory a processor moves between memory and its caches.
Reading one byte brings in the whole line. [ch02](#batches-in-memory)

**Cache miss.** A read whose cache line is not in the cache, so the whole line is fetched from
memory first. [ch02](#batches-in-memory)

**Cardinality estimate.** The number of rows a planner expects an operator to produce, made
before the query runs. [ch01](#the-plan-is-the-map)

**Column index.** Part of a Parquet file's page index: the smallest and largest value of each
page of a column chunk. [ch04](#statistics-and-pruning)

**Data page.** The unit a Parquet column chunk is stored in: a run of a column's values, encoded
and compressed together. [ch04](#statistics-and-pruning)

**Dictionary page.** The page of a dictionary-encoded column chunk that holds its distinct
values, which every data page of the chunk refers to by number. [ch04](#statistics-and-pruning)

**Filter.** The operator that keeps the rows for which a predicate is true.
[ch01](#the-plan-is-the-map)

**Filter pushdown.** Testing a query's predicates inside the scan, so it hands up only the rows
that pass. [ch03](#projection-and-filter-pushdown)

**Gather.** Reading rows by position, in an order given by a list of positions: row `k` of the
output is row `positions[k]` of the input. A sort, a join and a lookup each end in one.
[ch02](#batches-in-memory)

**Offset index.** Part of a Parquet file's page index: where each page of a column chunk starts,
and the first row it holds. [ch04](#statistics-and-pruning)

**Offsets.** The buffer of a string array that says where each row's bytes start and end in its
data buffer. [ch02](#batches-in-memory)

**Operator.** One step of a plan: a job with one input and one output, such as a scan, a filter
or a projection. [ch01](#the-plan-is-the-map)

**Physical plan.** The operators an engine will run for a query, and how rows flow between them.
DuckDB draws it for `EXPLAIN`. [ch01](#the-plan-is-the-map)

**Predicate.** A condition that each row either meets or does not, such as
`status = 'returned'`. [ch01](#the-plan-is-the-map)

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

**Validity bitmap.** One bit per value in an Arrow array, saying whether the value is present or
null. [ch02](#batches-in-memory)
