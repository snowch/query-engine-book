---
title: The plan is the map
---

(the-plan-is-the-map)=
# The plan is the map

:::{div}
:class: unwritten-note

This chapter is a draft. The question and the experiment are written; the sections from
*Building it* on are the plan for the rest.
:::

## The question

What does an engine do with your query, and where can you see what each step costs?

You hand an engine a sentence of SQL and it hands back rows. Between the two it does a fixed
sequence of jobs: read some columns, throw away some rows, compute some values. Each job has a
cost you pay in bytes read and rows moved. Every later chapter changes one of those jobs and
measures what moved. That needs two things first: a map of the jobs for a real query, and a way
to count what flows between them. DuckDB gives you both before you build anything.

## Observe

The query asks for the returned orders whose unit price was over a threshold. It reads
`orders-sorted`, one of the book's fixtures: a year of orders, one row each, written by a real
Parquet writer from a seeded generator. The query is a file in the repository, and this page
quotes it, so the SQL you read is the SQL every figure below ran.

```{literalinclude} ../queries/returned_unit_price.sql
:language: sql
```

Ask DuckDB how it will run the query, without running it, by putting `EXPLAIN` in front. What
comes back is the **physical plan**: the steps the engine will take, each drawn as a box. Each
box is an **operator**, one job with one input and one output. Rows flow from the bottom box to
the top one.

```{include} _generated/returned-unit-price-plan.md
```

Read the plan from the bottom, as the rows travel, and three things stand out.

1. **The scan reads fewer columns than the file has.** The `Projections` list in the scan box
   names the columns it passes up. `note` and `order_date` are not there: nothing above needs
   them, so the scan never reads them.
2. **One predicate moved into the scan.** `status = 'returned'` compares a column with a
   constant, and the plan lists it under the scan's `Filters`. The scan tests each row as it
   reads it and passes up only the rows that match. `status` is read for that test and then
   dropped. The unit price predicate divides one column by another, and it gets an operator of
   its own, `FILTER`.
3. **Every box ends with a guess.** The number after `~` is the operator's **cardinality
   estimate**: how many rows the planner expects the operator to produce. It was made before a
   single row was read.

A plan tells you what the engine intends. To see what it did, you run the query with profiling
on. DuckDB then writes a **profile**: the same tree of operators, each with counters from the
run. The book runs every query through one function, which asks for the plan, then runs the
query once with a JSON profile and reads it back:

```{literalinclude} ../python/query_lab/reference.py
:language: python
:start-at: def observe(
```

The profile's counters are the measurement in the next section. Before you look at them, you
make a prediction.

## Predict, then measure

Before you see what DuckDB measured, predict it: the rows that come out of the scan, out of the
filter, and out of the projection. You have what you need. The generator wrote the orders from
this recipe:

```{include} _generated/orders-recipe.md
```

The scan keeps the returned orders, so its output is the returned share of all the orders. The
filter keeps the returned orders whose unit price, `amount / quantity`, is over the query's
threshold. The unit price was drawn evenly across its range, so the share that passes is the
share of that range above the threshold. The projection computes a column and drops two; it
does not change the number of rows.

The panel holds the run. Each operator shows the planner's estimate, which `EXPLAIN` printed
before the query ran, and a box for your prediction. The measurement stays hidden until you
reveal it. Then each operator has three bars on one scale: your prediction, the planner's
estimate and the measurement. The profile names the scan `TABLE_SCAN`, where the plan drew it as
`PARQUET_SCAN`.

```lab
experiment: plan
query: returned_unit_price.sql
```

The panel draws what DuckDB measured when the book was built. Its button runs the same report
again in your browser, under Pyodide, and says whether your browser's DuckDB gave the same
answer. You can also edit the query and run your own. At a desk, the same numbers come from:

```bash
PYTHONPATH=python python3 -m query_lab observe queries/returned_unit_price.sql
```

Compare the three bars on each operator.

- **A prediction from the recipe is close to the measurement, and the plan's estimate is
  not.** You knew how the data was generated. DuckDB did not know how `status` and the unit price are distributed,
  so it guessed.
- **Each estimate is the same share of the estimate below it.** With nothing better to go on,
  the planner gave both predicates one default **selectivity**, the fraction of rows a predicate
  keeps. The chapters on planning are about where better estimates come from, and what a bad one
  costs when it chooses between plans.
- **Rows in, for each operator above the scan, is the output of the operator below.** Nothing is
  lost between boxes. That makes the profile a ledger: each operator's reduction is its rows out
  against its rows in.
- **Rows in, for the scan, is every row in the file.** That is DuckDB's report of the rows in the
  files it opened. [ch03](#projection-and-filter-pushdown) shows that it stays the same when the
  scan skips most of the file, so it tells you what the scan was responsible for, not what it
  decoded.

Keep your three numbers. When you build the same plan in the next section, your operators report
the same counters, and they must agree with these.

## Building it

[To write: A hand-written plan of scan, filter and projection over Arrow batches, each operator reporting its counters, checked against DuckDB's plan and profile.]

## Compare

[To write: the engine's results and counters beside DuckDB's.]

## What this cannot tell you

[To write: what the experiment, the model and the code leave out.]

## What this means for your design

[To write: the choices in the reader's own systems that this changes.]

## Key takeaways

[To write: the claims made and shown above, each in bold with its reason.]

## Problems

[To write: problems as stubs in `exercises/the_plan_is_the_map.py`, graded by `exercises/tests/test_the_plan_is_the_map.py`, and one diagnose-the-slow-query problem.]

## Where to go next

[To write: papers, engine source code, and the optional depth in the companion books.]
