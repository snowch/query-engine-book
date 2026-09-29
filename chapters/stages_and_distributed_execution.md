---
title: Stages and distributed execution
---

(stages-and-distributed-execution)=
# Stages and distributed execution

## The question

How does a distributed engine run a whole plan across many machines, and what does it do when one
of them fails partway through?

[ch15](#partitioning-and-shuffle) and [ch16](#skew) moved rows for one operator at a time. A real
query has several places where rows must move: its joins, its aggregates, its final sort. This
chapter cuts a plan at those places, runs the pieces one after another on simulated nodes, and
counts what a failed node costs, depending on where the moved rows were kept.

## Observe

The query asks what each country's customers spent, largest first:

```{literalinclude} ../queries/spend_by_country.sql
:language: sql
```

DuckDB's plan, on one machine:

```{include} _generated/spend-by-country-plan.md
```

1. **Three operators need rows to meet.** The hash join needs each customer's orders with the
   customer; the aggregate needs each country's rows together; the sort needs every country's
   total in one place.
2. **On one machine, meeting is free.** DuckDB's operators read the rows from memory, wherever its
   threads put them.
3. **Across machines, each of those three is a shuffle.** Below the join, both tables must move by
   customer; below the aggregate, the joined rows by country; below the sort, the totals to one
   node. A distributed engine cuts its plan at each.

The operators between two such cuts, run the same way on every node over that node's rows, are a
**stage**. One node's run of a stage is a **task**.

## Predict, then measure

Your engine runs the query in four stages on sixteen simulated nodes:

```{include} _generated/spend-by-country-stages.md
```

The rows each stage shuffles on must be kept until the next stage reads them. An engine may pass
them straight on, keeping them nowhere; keep them on the disk of the node that wrote them; or
write them to storage every node can read.

A node dies while the third stage runs. Predict how many tasks each way of keeping the rows must
run again. The panel shows the tasks in the whole query beside each.

```lab
experiment: measure
of: stages
```

The panel draws what your engine counted when the book was built. Its button runs the same stages
again in your browser.

- **Kept nowhere, the query starts again.** Nothing the first two stages made survives, so every
  task so far runs again. This is the cheapest way to run when nothing fails.
- **Kept on the node, only the dead node's work is redone.** Its task in each stage so far, since
  what it wrote died with it. Every other node's output is still on its disk.
- **Kept in shared storage, one task runs again.** Everything the earlier stages wrote survives the
  node. It costs writing every shuffled byte to storage, and reading it back.
- **The chart moves the failure.** The later a failure, the more a query that keeps nothing loses.
  The other two lose little, wherever it comes.

## Building it

### The stages

The engine runs each stage over every node, then shuffles its output for the next. The first reads
each node's part of both tables and shuffles them by customer; the second joins and aggregates in
part, and shuffles by country; the third finishes the aggregate and gathers the countries; the
fourth sorts them, as one task:

```{literalinclude} ../python/query_lab/stages.py
:language: python
:start-at: def spend_by_country(
:end-before: #: Where a stage's shuffled output is kept
```

The second stage is ch15's two-phase aggregate, joined first: each node sends a row per country,
not a row per order.

### A failure

What a failed node costs follows from where the rows between stages were kept:

```{literalinclude} ../python/query_lab/stages.py
:language: python
:start-at: def rerun(
```

```run
experiment: measure
of: stages
```

Suppose the node's disk survives it, as with a shuffle service that keeps its files, and change
the second case to return `1`, and run the panel's report on your edit: keeping rows on the node
becomes as safe as shared storage, as long as the disk outlives the node.

## Compare

DuckDB runs on one machine, and its plan has no stages. The engines that do run stages differ in
exactly the choice the panel measured:

- **Apache Spark keeps rows on the node.** Each stage writes its shuffled output to local disk, and
  a lost node's tasks are run again from the stage that made the lost files. Its external shuffle
  service keeps those files on disk even when the process that wrote them dies.
- **Trino passes rows straight on.** Its stages run at once, streaming pages from one to the next,
  which is fast, and a failure fails the query. Its fault-tolerant mode instead writes each stage's
  output to shared storage and retries tasks, at the cost of the writing.
- **Apache DataFusion's Ballista plans stages as Spark does**, from a DataFusion plan, and keeps
  each stage's output until the next stage has read it.

The book's tests check that the stages give DuckDB's rows on one node, four and sixteen.

## What this cannot tell you

- **How long each choice takes.** Writing shuffled rows to disk or storage costs time the counts
  do not show, and it is why engines that pass rows straight on are faster when nothing fails.
- **How often nodes fail.** On a few machines for a few minutes, rarely; on thousands for hours,
  often. The right choice depends on which.
- **How stages run at once.** Stages that read different tables can run side by side; the
  simulation runs them in turn. Problem 17.2 counts what running them at once saves.

## What this means for your design

- **Count the shuffles in your plan.** Each join, aggregate and sort on a key the data is not
  partitioned by is a stage boundary, and every row crossing it moves.
- **Aggregate early.** ch15's two phases shrink what crosses the boundary between the join and the
  aggregate from a row per order to a row per country per node.
- **Match fault tolerance to the job.** Short interactive queries are cheaper to rerun than to
  protect; long batch jobs on many machines are not.
- **Partition to avoid stages.** A table already partitioned by the join key needs no shuffle below
  the join, and loses a stage.

## Key takeaways

:::{div}
:class: takeaways

- **A distributed plan is cut into stages at every shuffle.** Each stage runs as a task on every
  node.
- **The rows between stages must be kept somewhere.** Passed on, on the node, or in shared storage.
- **Where they are kept decides what a failure costs.** From the whole query to a single task.
- **Keeping them costs writing them.** Speed when nothing fails and safety when something does
  pull in opposite directions.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: stages_and_distributed_execution
```

**17.1 Cut the stages.** Write `cut_stages`: given a plan with its exchanges marked, the stages it
runs as, each after the stages it reads. The graders cut the chapter's plan and many random ones,
and check every operator is in one stage, no stage crosses an exchange, and the order is one an
engine could run.

**17.2 Stages at once.** Write `finish_time`: given each stage's steps and the stages it reads,
when the last finishes, if every stage starts as soon as its inputs are ready. The graders step a
simulated clock through the chapter's stages and many random ones, and compare.

**17.3 Diagnose the lost hour.** No test. A nightly report runs for an hour on a hundred machines,
in an engine that passes rows straight on between stages. Once a week a machine fails near the
end, and the report runs again from the start. Using the panel's chart, explain what each failure
costs, and what keeping the rows on the node or in shared storage would cost every night instead.
What would you choose, and what would you need to know to be sure? A good answer weighs the chance
of a failure against the cost of writing every shuffled byte, and names both of the other choices'
risks.

## Where to go next

- **Stages and lineage.** Matei Zaharia and others, *Resilient Distributed Datasets: A
  Fault-Tolerant Abstraction for In-Memory Cluster Computing*, NSDI 2012: Spark's stages, and
  recomputing what a failure loses.
- **Streaming between stages.** Raghav Sethi and others, *Presto: SQL on Everything*, ICDE 2019:
  stages that run at once and stream, and what that trades away.
- **A distributed engine to read.** Apache DataFusion's
  [Ballista](https://datafusion.apache.org/ballista/), built on the same Arrow the book's engine
  uses, and Andy Grove's *How Query Engines Work*, which ends with it.
