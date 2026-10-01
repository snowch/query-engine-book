---
title: Parallelism on one machine
---

(parallelism-on-one-machine)=
# Parallelism on one machine

## The question

How much faster does a query finish with more cores, and what stops it going faster still?

Every run so far used one thread: DuckDB in this page has one, and the book builds its figures
with one too, so that both agree. A machine with sixteen cores could, in principle, finish a query
sixteen times sooner. This chapter asks what a query must be split into for cores to
share it, and what part of it no number of cores can share. It times nothing: your browser
runs one thread, so there is no second core to time. It counts the work each would do.

## Observe

ch07's query, run by DuckDB with one thread and with four, at build time:

```{include} _generated/threads.md
```

1. **The plan is the same, and so is every row.** Four threads run the same operators and hand
   up the same rows from each. Parallelism is not in the plan: it is in how the plan's work is
   divided while it runs.
2. **The unit DuckDB divides a Parquet scan into is the row group.** Each thread takes a row
   group, runs the operators above the scan on its rows, and takes the next. The sorted orders
   are ten row groups; the paged orders, from ch04, are one.
3. **The aggregate cannot finish on any one thread.** Each thread builds a table of the groups
   in its own row groups. The tables must then be combined into one, and a customer whose orders
   fell to several threads is in several tables.

A slice of the input one worker takes at a time is a **morsel**, here one row group. The run of
operators a morsel passes through, from the scan up to the first operator that must see all of
its input, is a **pipeline**. How many times sooner a query finishes with several workers than
with one is its **speedup**.

## Predict, then measure

Your engine simulates the workers. Each takes the next morsel as soon as it is free and runs a
pipeline on it; the work of a morsel is the rows each operator takes in, the counter every
operator already keeps. A query is done when its busiest worker is, and then any combining.

Predict the work until each of three queries is done, with four workers: ch01's returned
orders on the sorted orders; ch07's orders per customer on the same file; and the returned orders
on the paged orders, one row group. The panel shows the work on one worker beside each.

```lab
experiment: measure
of: parallelism
```

The panel draws what your engine counted when the book was built. Its button runs the same
workers again in your browser.

- **Ten morsels do not divide by four.** Two workers take three morsels and two take two, so the
  query finishes after three morsels' work, not two and a half. The chart's first line climbs in
  steps: eight workers are no faster than six, and nothing beats ten.
- **The aggregate pays for combining.** Each worker's table holds most of the customers, so the
  combining takes in a row for nearly every customer from every worker. More workers, more tables
  to combine, and the combining is one worker's job.
- **One row group is one morsel.** One worker does everything, however many there are. A file
  written as one large row group, as ch04's was for its page index, gives a parallel reader
  nothing to share.

## Building it

### A morsel

A morsel is one row group of the file, read and handed to a pipeline as its only batch:

```{literalinclude} ../python/query_lab/parallel.py
:language: python
:start-at: class Morsel(Operator):
:end-before: @dataclass
```

### The workers

Each morsel, in order, goes to the worker whose work so far is least, which is the one that will
be free soonest:

```{literalinclude} ../python/query_lab/parallel.py
:language: python
:start-at: def assign(
:end-before: def work_of(
```

```run
experiment: measure
of: parallelism
```

Give each morsel to the busiest worker instead, `max` in place of `min`, and run the panel's
report on your edit: one worker does everything, and no query is faster than on one.

### A run

A run makes a pipeline for every morsel, counts each pipeline's work, and hands the morsels to
the workers. For an aggregate, it then counts the combining: a row for every group in every
worker's table:

```{literalinclude} ../python/query_lab/parallel.py
:language: python
:start-at: def run(
```

The book's tests check that the morsels together hand up DuckDB's rows, that one worker has
nothing to combine, and that more workers combine more.

## Compare

DuckDB's counters were the same with one thread and four; its plan did not change. Your
simulation says what the four threads did with it:

- **Both divide the scan by row group.** DuckDB's Parquet reader hands out row groups to its
  threads, as your workers take morsels.
- **Both combine the aggregate's tables at the end.** DuckDB's hash aggregate partitions each
  thread's table by the keys' hashes, so the combining can itself be shared out, a partition to a
  thread. Your simulation leaves it to one worker, which is the worst case.
- **Neither can split one row group.** A file of one row group runs on one thread in DuckDB 1.1.2
  too, however many it is given.

## What this cannot tell you

- **How long anything takes.** The work is counted in rows. Real threads share memory bandwidth,
  caches and the file, and do not each run as fast as one alone.
- **What waiting costs.** Real workers wait for a lock, a shared queue or each other. The
  simulated ones never wait, except for the combining.
- **How DuckDB schedules.** DuckDB's scheduler runs pipelines in pieces, and can run parts of
  different pipelines at once. The simulation runs one pipeline and its combining.

## What this means for your design

- **Write files with many row groups.** A reader splits a file by row group; one large row group
  is one core's work. Many small files split the same way.
- **Aim for more morsels than cores.** With few morsels the last ones leave cores idle. Several
  per core keeps them busy to the end.
- **Mind what cannot be shared.** Combining partial results, a final sort's merge, the last
  step of a top-k: whatever waits for every worker sets the limit on the speedup, as Gene Amdahl
  observed.
- **Group by fewer keys where you can.** Each worker's table holds its share of the groups, and
  combining takes a row for each; many groups make many rows to combine.

## Key takeaways

:::{div}
:class: takeaways

- **Parallelism divides a plan's work, not the plan.** The same operators and the same rows,
  shared among workers.
- **The unit of sharing is the morsel.** For a Parquet scan, a row group: no more workers are
  useful than there are row groups.
- **Uneven shares cost the most.** A query is done when its busiest worker is.
- **What waits for every worker limits the speedup.** Combining partial results is one worker's
  work, and grows with the workers.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: parallelism_on_one_machine
```

**14.1 Split the row group.** Write `split`: cut each row group into morsels of at most a given
number of rows, so that one large row group keeps several workers busy. The graders check every
row is covered once, and that the paged orders' one row group, split, gives four workers nearly
four times the speed.

**14.2 A top-k on every worker.** Write `local_top` and `merge_tops`: each worker keeps the largest
orders of its own morsels, and one merge finds the largest of all. The graders run your workers on
the shuffled orders, check none holds more than it should, and compare the merged rows with
DuckDB's `ORDER BY ... LIMIT`.

**14.3 Diagnose the idle machine.** No test. A team moved its orders to a sixteen-core machine,
and the report on them runs no faster. Their file is ch04's paged orders. Using the panel's chart
and the row groups in the figure above, explain why. What would you change about the file, and
what about the report's aggregate, to use the cores? A good answer names the single row group,
proposes a row group size that gives several morsels per core, and says what the combining will
still cost.

## Where to go next

- **Morsels.** Viktor Leis, Peter Boncz, Alfons Kemper and Thomas Neumann, *Morsel-Driven
  Parallelism: A NUMA-Aware Query Evaluation Framework for the Many-Core Age*, SIGMOD 2014: the
  scheduling this chapter simulates, and DuckDB's model.
- **The limit.** Gene Amdahl, *Validity of the Single Processor Approach to Achieving Large Scale
  Computing Capabilities*, AFIPS 1967: the part that cannot be shared sets the speedup.
- **DuckDB's pipelines.** DuckDB's [source](https://github.com/duckdb/duckdb), in
  `src/parallel/`: how a plan is cut into pipelines at the operators that must see all their
  input, and how its threads take pieces of them to run.
