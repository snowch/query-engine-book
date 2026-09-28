---
title: Glossary
---

(glossary)=
# Glossary

Terms the book uses, each with the chapter that introduces it. No chapter uses a term before the
chapter that introduces it: `tests/test_book.py` checks every entry.

**Batch.** A slice of a table, a few thousand rows held column by column as Arrow arrays: what
one operator hands the next. [ch01](#the-plan-is-the-map)

**Cache line.** The fixed-size block of memory a processor moves between memory and its caches.
Reading one byte brings in the whole line. [ch02](#batches-in-memory)

**Cardinality estimate.** The number of rows a planner expects an operator to produce, made
before the query runs. [ch01](#the-plan-is-the-map)

**Operator.** One step of a plan: a job with one input and one output, such as a scan, a filter
or a projection. [ch01](#the-plan-is-the-map)

**Physical plan.** The operators an engine will run for a query, and how rows flow between them.
DuckDB draws it for `EXPLAIN`. [ch01](#the-plan-is-the-map)

**Profile.** A plan's operators after a run, each with counters from that run.
[ch01](#the-plan-is-the-map)

**Pull model.** Running a plan by having each operator ask the one below it for a batch when it
needs one, so the top of the plan drives the run. [ch01](#the-plan-is-the-map)

**Pushdown.** Handing work to the operator that reads the data, so that data never has to leave
it. [ch03](#projection-and-filter-pushdown)

**Row group.** A horizontal slice of a Parquet file: every column's values for a run of rows,
with statistics for each column. [ch01](#the-plan-is-the-map)

**Selectivity.** The fraction of its input rows a predicate keeps. [ch01](#the-plan-is-the-map)

**Validity bitmap.** One bit per value in an Arrow array, saying whether the value is present or
null. [ch02](#batches-in-memory)
