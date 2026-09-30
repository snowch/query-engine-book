---
title: Pushing instead of pulling
---

(pushing-instead-of-pulling)=
# Pushing instead of pulling

## The question

What changes when the scan drives the query, pushing rows up the plan, instead of the top asking
for them?

Every operator you have built pulls. [ch01](#the-plan-is-the-map)'s projection asked its filter for
a batch, the filter asked the scan, and nothing was read until the top of the plan asked. DuckDB
runs its plans the other way round: the scan loops over the file and hands each batch to the
operator above it, which hands its result on, until the batch reaches an operator that keeps it.
The operators and the rows are the same. What changes is who holds the loop, and this chapter
counts what follows from that.

## Observe

Two questions about the returned orders. The first needs every returned order:

```{literalinclude} ../queries/returned_count.sql
:language: sql
```

The second needs only one:

```{literalinclude} ../queries/any_returned.sql
:language: sql
```

DuckDB plans the second like this:

```{include} _generated/any-returned-explain.md
```

A third asks for the customers whose returns add up to more than the average returned order. It
reads the returned orders twice, once for each customer's total and once for the average:

```{literalinclude} ../queries/big_returners.sql
:language: sql
```

Its twin asks DuckDB to read the returned orders once and keep them:

```{literalinclude} ../queries/big_returners_materialized.sql
:language: sql
```

What DuckDB read for each, and how many scans its plan has:

```{include} _generated/pushing-bytes.md
```

1. **The question that needs one row read a fraction of what the count read.** The
   `STREAMING_LIMIT` above the scan keeps one row, and the scan stopped soon after. Something had
   to tell it to stop: in DuckDB, the scan is not asked for rows, it hands them up.
2. **Two consumers of one input, two scans.** Written plainly, the returned orders feed two
   parts of the plan, and each reads them from the file: nearly twice the bytes.
3. **Kept, they are read once, and scanned twice.** `MATERIALIZED` reads the file once into a
   result DuckDB holds in memory, and two `CTE_SCAN`s read that result. It saves the second read
   by holding every returned order until both consumers are done.

Running a plan by having the operator at the bottom hand each batch up to the operator above it,
and so on to the top, is the **push model**. An operator that keeps what it is handed, instead of
handing it on, is a **sink**: an aggregate's table, a join's build side, the query's result.

## Predict, then measure

Your engine pushes both queries. The scan tests the status, as in
[ch03](#projection-and-filter-pushdown), and pushes each row group's returned orders on. For the
first query, the sink wants one row; the panel runs it with a source that listens when the sink
says it has enough, and with one that never listens. For the second, it runs two consumers of the
returned orders pulled, each asking its own scan, and pushed, through one scan that hands every
batch to both.

Predict the bytes each way reads. The panel shows the bytes of reading to the end, or of one scan,
beside each.

```lab
experiment: measure
of: pushing
```

The panel draws what your engine counted when the book was built. Its button runs the same
pipelines again in your browser.

- **A source that listens stops after the first row group with a returned order.** It read the
  footer and one row group's statuses. The one that never listens reads every row group, and its
  sink ignores every row after the first.
- **Pulled, each consumer pays for its own scan.** Two consumers, twice the bytes; the chart's
  rising line adds a scan's worth for each consumer more.
- **Pushed, one scan serves every consumer.** The flat line: the tee hands each batch to every
  consumer, and each takes in every returned order, from one read of the file.

## Building it

### A step

A pushed operator is a step: it is handed a batch, does its work, and pushes the result to the
steps after it. What it returns is its answer to one question: does anything after it want more?

```{literalinclude} ../python/query_lab/push.py
:language: python
:start-at: class Step:
:end-before: def drive(
```

Steps keep the same counters as pulled operators, and the same ledger holds: each step's rows in
are the rows handed to it.

### The source's loop

In a pulled plan, the loop is at the top: the result asks for batches until there are none. In a
pushed pipeline, the loop is at the bottom, in the source, and it is the only place a pipeline can
stop:

```{literalinclude} ../python/query_lab/push.py
:language: python
:start-at: def drive(
:end-before: class Filter(
```

```run
experiment: measure
of: pushing
```

Make the source deaf, changing `if listen and not wants_more:` to `if False:`, and run the panel's
report on your edit: the first case reads to the end, as the second always did. In a pulled plan,
stopping is free, since a scan nobody asks reads nothing more. In a pushed one, it is a message
the source must be written to hear.

### Steps and sinks

A filter is a step that pushes on what passes. The sink that answers whether a row exists wants
none once it has one:

```{literalinclude} ../python/query_lab/push.py
:language: python
:start-at: class Filter(
:end-before: class Tee(
```

```{literalinclude} ../python/query_lab/push.py
:language: python
:start-at: class Exists(
:end-before: class Group(
```

### One scan, two consumers

A **tee** hands every batch it is pushed to each step after it, and wants more while any of them
does:

```{literalinclude} ../python/query_lab/push.py
:language: python
:start-at: class Tee(
:end-before: class Exists(
```

The query's two consumers are ch07's hash aggregate, rewritten as a sink: the same loop, run on
each batch as it is pushed, instead of on each batch it pulls. The first pipeline reads the file
once and fills both:

```{literalinclude} ../python/query_lab/push.py
:language: python
:start-at: def big_returners(
:end-before: def big_returners_pulled(
```

### Pipelines

An aggregate cannot push anything on until its source has run dry, since any row might belong to
any group. It ends the pipeline, and its groups are the source of the next one. An operator that
must see all its input before it hands anything up is a **pipeline breaker**, and a pushed plan is
cut into pipelines at every one: aggregates, sorts, and the build side of a hash join. The second
pipeline starts from the totals the first one left in its sink:

```{literalinclude} ../python/query_lab/push.py
:language: python
:start-at: def over_average(
:end-before: def result_of(
```

The book's tests check that both queries give DuckDB's answers, pushed and pulled, that every
consumer of the tee takes in every row the scan hands up, and that pulled consumers read one scan's
bytes each.

## Compare

Your engine's bytes, beside DuckDB's:

```{include} _generated/pushing-compare.md
```

- **Both stop a scan for a sink that has enough.** DuckDB's `STREAMING_LIMIT` tells its scan it
  is finished, as your `Exists` tells your source. Each reads a little of the file beyond its
  footer; the two readers fetch it in different pieces.
- **Your tee and DuckDB's kept result read the same bytes.** Both read the returned orders'
  columns once. They differ in what they hold: your tee holds one batch at a time, and DuckDB's
  materialised result holds every returned order until both consumers have read it.
- **Pulled, both read the file twice.** Your two scans read it twice in full; DuckDB's second
  read is a little smaller than its first.
- **DuckDB's operators answer as your steps do.** Each of its operators returns whether it needs
  more input or has finished, and each sink whether it wants more, and its pipeline's loop stops
  on the answer.

## What this cannot tell you

- **Which model is faster.** Pulling and pushing do the same work on the same batches; the
  counters cannot tell them apart where both read the same bytes. The difference in time lies in
  the calls between operators, and the book does not time them.
- **What a tee costs when its consumers are uneven.** Your tee pushes every batch to every
  consumer at once. If one consumer is slower, a real engine must hold batches for it, or slow the
  others down.
- **How DuckDB decides when to keep a result.** DuckDB 1.1.2 reads a `WITH` twice unless told
  otherwise. Other engines, and other versions, may decide for themselves, weighing a second read
  against the memory a kept result holds.

## What this means for your design

- **Ask for what you need, and the engine can stop early.** `EXISTS`, `LIMIT` without `ORDER BY`,
  and a join that needs one match are all ways of saying so. Problem 18.3 shows a limit that
  cannot stop.
- **Know how your engine treats a `WITH` used twice.** Some read its input again for every use;
  some keep the result in memory. Either can be the right choice; check which yours made, in its
  plan.
- **Read a plan's pipeline breakers.** Aggregates, sorts and a join's build side each end a
  pipeline, and each holds its input, or what it made of it, until the pipeline is done. The
  memory of [Part III](#part-computing) is held there.
- **Expect push engines to parallelise by pipeline.** DuckDB's workers, as
  [ch14](#parallelism-on-one-machine) simulated them, each take a morsel and push it through a
  pipeline to its sink. A loop at the source is what lets a scheduler hand out the work.

## Key takeaways

:::{div}
:class: takeaways

- **Push turns the loop upside down.** The source loops over its input and hands each batch up;
  the operators and the rows stay the same.
- **Stopping becomes a message.** A sink that has enough must say so, and the source must listen,
  or it reads to the end.
- **One source can feed several consumers.** A tee serves them from one scan, where pulled
  consumers each read the input again.
- **A pushed plan is cut into pipelines at its breakers.** Each breaker is a sink for one
  pipeline and the source of the next.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: pushing_instead_of_pulling
```

**18.1 Push a hash join.** Write `Build` and `Probe`: the build side of ch08's hash join as a sink,
which ends its pipeline, and the probe side as a step in the next. The graders build the customers,
push the orders through your probe, and compare the rows with DuckDB's join; they check the probe
refuses to start before the build side is ready, and passes on a sink's answer when it has enough.

**18.2 Gather the crumbs.** A selective filter pushes on batches of a few rows each, and every
batch costs every step above it a call. Write `Coalesce`: a step that gathers small batches until
they hold a given number of rows, then pushes them on as one. The graders push random batches
through it and after the returned orders' filter, and check no row is lost or reordered, no batch
goes on early or late, and a sink's answer comes back through it.

**18.3 Diagnose the limit that read everything.** No test. A colleague asks for any ten orders,
and then for the ten earliest:

```{literalinclude} ../queries/earliest_orders.sql
:language: sql
```

```{include} _generated/earliest-orders.md
```

The file is sorted by date, and the ten earliest orders are all in its first row group. Why did
DuckDB read every row group for them, and only one for any ten? What would an engine need to know,
and to do, to stop after the first row group? A good answer names the operator that breaks the
pipeline, says why it cannot tell the scan to stop, and uses each row group's range of dates to
say when the scan could stop, as [ch04](#statistics-and-pruning) used the same statistics to
skip.

## Where to go next

- **Push-based execution.** Thomas Neumann, *Efficiently Compiling Efficient Query Plans for
  Modern Hardware*, VLDB 2011: pipelines, pushed from the source to each breaker, as the unit an
  engine runs. [ch19](#compiling-a-query) takes up the rest of the paper.
- **Morsels and pipelines.** Viktor Leis, Peter Boncz, Alfons Kemper and Thomas Neumann,
  *Morsel-Driven Parallelism*, SIGMOD 2014: a scheduler handing pipelines' morsels to workers.
- **Push and pull compared.** Amir Shaikhha, Mohammad Dashti and Christoph Koch, *Push versus
  Pull-Based Loop Fusion in Query Engines*, Journal of Functional Programming, 2018: the same
  plans run both ways, and where each stops early or not.
- **DuckDB's pipelines.** DuckDB's [source](https://github.com/duckdb/duckdb), in
  `src/parallel/pipeline_executor.cpp`: the loop that pushes a source's chunks through a
  pipeline's operators into its sink, and stops when the sink says it is finished.
