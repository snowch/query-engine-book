---
title: The plan is the map
---

(the-plan-is-the-map)=
# The plan is the map

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
comes back is the **physical plan**: the steps the engine will take, one to a row of the table
below. Each step is an **operator**, one job with one input and one output. Rows flow from the
bottom operator to the top one.

This plan has one operator for each of the three jobs in the question. A **scan** reads rows
from storage: here, from the Parquet file. A **filter** keeps the rows for which a
**predicate** is true, where a predicate is a condition, such as `status = 'returned'`, that
each row either meets or does not. A **projection** computes the columns the query returns
from the columns it is given, and drops the rest. DuckDB calls them `PARQUET_SCAN`, `FILTER` and
`PROJECTION`.

```{include} _generated/returned-unit-price-plan.md
```

Read the plan from the bottom, as the rows travel, and three things stand out.

1. **The scan reads fewer columns than the file has.** The `Projections` list in the scan's row
   names the columns it passes up. `note` and `order_date` are not there: nothing above needs
   them, so the scan never reads them.
2. **One predicate moved into the scan.** `status = 'returned'` compares a column with a
   constant, and the plan lists it under the scan's `Filters`. The scan tests each row as it
   reads it and passes up only the rows that match. `status` is read for that test and then
   dropped. The unit price predicate divides one column by another, and it gets an operator of
   its own, `FILTER`.
3. **Every operator comes with a guess.** The second column is the operator's **cardinality
   estimate**: how many rows the planner, the part of the engine that turned the SQL into this
   plan, expects the operator to produce. It was made before a
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

In the chapters that follow, you predict what an operator will do before you measure it. Here
the prediction is the planner's: `EXPLAIN` printed an estimate for each operator before the
query ran, and running the query measures what each operator did. The panel sets the two side by
side, operator by operator. The profile names the scan `TABLE_SCAN`, where the plan drew it as
`PARQUET_SCAN`.

```lab
experiment: plan
query: returned_unit_price.sql
variants: pricier_returns.sql, shipped_unit_price.sql
```

The panel draws what DuckDB measured when the book was built. Its button runs the same report
again in your browser, under Pyodide, and says whether your browser's DuckDB gave the same
answer.

Above the plan are changes to try: a higher price threshold, and shipped orders in place of
returned ones. Each one redraws the plan at once, from a run the book made when it was built.
Try them, and watch which numbers move.

- **The measurements move, and the estimates do not.** Whichever orders you ask for, the planner
  expects the same rows from the scan and the same rows from the filter. It knows how many rows
  the file holds, and nothing about how `status` or the unit price are spread across them. So it
  gives every predicate the same default **selectivity**, the fraction of rows a predicate keeps.
- **An estimate can be wrong in either direction.** For the returned orders it is too high; for
  the shipped ones it is far too low. A planner that chooses between plans with guesses like
  these can choose the wrong one. The chapters on planning are about where better estimates come
  from.
- **Rows in, for each operator above the scan, is the output of the operator below.** Nothing is
  lost between operators. That makes the profile a ledger: each operator's reduction is its rows
  out against its rows in.
- **Rows in, for the scan, is every row in the file.** That is DuckDB's report of the rows in the
  files it opened. [ch03](#projection-and-filter-pushdown) shows that it stays the same when the
  scan skips most of the file, so it tells you what the scan was responsible for, not what it
  decoded.

The measurements are no mystery. They follow from how the generator wrote the orders:

```{include} _generated/orders-recipe.md
```

The scan keeps the returned orders, which are the returned share of all the orders. The filter
keeps those whose unit price, `amount / quantity`, is over the query's threshold, which is the
share of the price range above it, since prices were drawn evenly across the range. The
projection changes no row count. You could have worked the measurements out from this recipe.
The planner could not, because nobody gave it the recipe. Later chapters give you what a
prediction needs before they ask you for one.

To go further, open the editor under the plan and run a query of your own. It runs in your
browser.

Keep the book's three measurements. When you build the same plan in the next section, your
operators report the same counters, and they must agree with these.

## Building it

Your engine runs the same plan, operator by operator. Each operator does one job and produces
one output: a stream of **batches**. A batch is a slice of a table, a few thousand rows held
column by column as Apache Arrow arrays, so an operator works on a column at a time instead of a
row at a time. Every operator in the book shares one shape:

```{literalinclude} ../python/query_lab/operators.py
:language: python
:start-at: class Operator:
:end-before: class Scan(Operator):
```

`batches` is a generator. An operator produces a batch only when the operator above it asks
for one, and it asks the operator below it, its child, for input only then. So the operator at the top drives the
run, and nothing is read until something above asks. This is the **pull model**: rows are pulled
up the plan, not pushed. `take` and `emit` count every batch on its way in and out, so every
operator reports the counters in COUNTERS.md without any code of its own for counting.

### The scan

The scan is the only operator that reads. A Parquet file is cut into **row groups**: horizontal
slices of the table, each holding every column's values for a run of rows, one column after
another. The scan opens the file with the Parquet reader from *Parquet, byte by byte*, through
that book's simulated object store, so every byte it reads is a request the store logged. It
reads the footer, which says where everything is, then, for each row group, the chunks of the
columns it was asked for. It decodes them and hands up one batch per row group.

```{literalinclude} ../python/query_lab/operators.py
:language: python
:start-at: class Scan(Operator):
:end-before: class Filter(Operator):
```

Called with no `filters`, as this chapter calls it, the scan reads every row group and hands up
every row. It tests no predicate, where DuckDB's did. That difference is the first thing the
comparison below shows, and the `filters` are how [ch03](#projection-and-filter-pushdown) closes
it.

### Filter and project

A filter asks its child for a batch. It evaluates its predicate for
every row with a kernel from `pyarrow.compute`, a function that works on a whole column at once,
and hands up the rows that are true. A projection computes each output column
from the batch it receives. Neither changes how many batches flow; only the filter changes how
many rows.

```{literalinclude} ../python/query_lab/operators.py
:language: python
:start-at: class Filter(Operator):
:end-before: def arrow_type(
```

### The plan

The engine has no planner yet, so you write the plan by hand, bottom up, the way `EXPLAIN` drew
DuckDB's. The scan reads the five columns the query uses. Two filters take the two predicates in
turn, and a projection computes the unit price:

```{literalinclude} ../python/query_lab/plans.py
:language: python
:start-at: def returned_unit_price(
:end-before: #: Each plan, by the query file it answers.
```

The book's tests run this plan every time the book is built. They check that its counters obey
COUNTERS.md's rules, and compare its result with DuckDB's, row for row. The comparison below is
what they found.

## Compare

Your engine returns DuckDB's rows, in DuckDB's order. The table puts each of your operators
beside the DuckDB operator that does the same job:

```{include} _generated/returned-unit-price-compare.md
```

- **Where the two plans do the same job, they count the same rows.** Your unit price filter and
  DuckDB's `FILTER` take the same rows in and hand the same rows out, and so do the two
  projections. The test holds every pair to it.
- **DuckDB has no partner for your scan.** Its scan tested `status = 'returned'` itself, so its
  output is the output of your first filter. Your scan hands every row of the file up to a
  filter that throws most of them away. [ch03](#projection-and-filter-pushdown) makes your scan do
  what DuckDB's did, and measures what it saves.

Your engine also counts what DuckDB's profile does not report: the batches each operator
produced, the bytes and requests the scan made, and the most memory each operator held:

```{include} _generated/returned-unit-price-engine.md
```

The scan read only the column chunks it asked for, which is a fraction of the file: the other
columns' bytes were never requested. The rows it handed up, and the bytes of every column of
every one of them, all went to the first filter, which kept few of them. The cheapest row to
filter is the one the scan never hands up.

## What this cannot tell you

- **How long anything took.** The counters say how much work each operator did, not how fast.
  Your engine decodes Parquet in Python, many times slower than DuckDB's C++, and its times would
  say nothing about the design. The chapters that are about time use small simulators; the book
  never prints a time.
- **What DuckDB's scan decoded.** DuckDB reports the rows in the files its scan opened, not the
  rows it decoded. [ch03](#projection-and-filter-pushdown) counts that with your own scan.
- **Anything about statistics.** Your scan, as this chapter uses it, reads every row group,
  whatever the query asks. It ignores the minimum and maximum the file records for each column.
- **Memory beyond Arrow's buffers.** Peak memory counts the Arrow buffers an operator holds. The
  reader decodes each column into Python values before your scan builds its arrays, and those
  are not counted.
- **Plans with more than one input, or more rows than memory.** One file, one thread, and every
  batch small. Joins, spilling and parallelism are later parts of the book.
- **How a planner chooses.** You wrote this plan. The planner that writes plans, and the
  statistics it guesses with, are Part IV.

## What this means for your design

- **Read the profile before you change anything.** Rows in and rows out, operator by operator,
  show where the work goes. The operator with the largest rows in, and the one that throws most
  of them away, are where a change pays.
- **Write predicates the scan can test.** DuckDB tested `status = 'returned'` inside its scan
  because the predicate compares a bare column with a constant. The unit price test needed a
  calculation first, so it waited for a filter, and every row the scan passed up reached it.
- **Ask only for the columns you need.** Your scan's bytes read are the column chunks it
  requested. Every extra column in a query is more bytes, in every row group.
- **Treat estimates as guesses.** The plan's estimates were far from what the profile measured.
  A plan chosen from guesses can be the wrong plan; the profile says whether it was.

## Key takeaways

:::{div}
:class: takeaways

- **A plan is a tree of operators, and rows flow up it.** The physical plan names each operator;
  the profile says how many rows each took in and handed out.
- **Estimates come before the run; counters come from it.** The planner's estimate and the
  measured rows can be far apart, and only the profile says which was right.
- **An engine pulls.** Each operator asks the one below it for a batch when it needs one, so
  nothing is read until something asks.
- **Where the two plans do the same job, they count the same rows.** That is what makes DuckDB a
  reference: your engine's counters are checked against it, operator by operator.
- **The scan decides how much everything above it does.** DuckDB's scan tested one predicate and
  handed up a small share of the file; yours handed up all of it.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there: they are the book's own tests, and they run in your browser. Your answers stay in this
browser, and **Reset to the stubs** starts again.

```problems
chapter: the_plan_is_the_map
```

**1.1 A limit.** Write `Limit`: an operator that hands up
the first `n` rows its child produces, and no more. It must stop asking its child for batches as
soon as it has `n` rows. The graders compare its rows with DuckDB's `LIMIT`, and count the
batches its child produced, with and without a filter between them. A limit that drains its
child fails even when its rows are right. This is where the pull model pays: a limit at the top
of a plan stops the scan at the bottom.

**1.2 A plan of your own.** Write `customer_orders`, the plan for every order of one customer:
`order_id`, `order_date` and `amount`, where `customer_id` equals the customer given. Build it
from the book's operators. The graders compare its result with DuckDB's for several customers,
check its counters obey the rules, and check the scan reads no column the query does not use.

**1.3 Diagnose the slow query.** No test. A colleague finds the same returned orders with this
query:

```{literalinclude} ../queries/lower_status.sql
:language: sql
```

It returns the same rows as the chapter's query, and DuckDB profiles it like this:

```{include} _generated/lower-status-profile.md
```

Which operator does more work than it did for the chapter's query, and why did DuckDB's scan
not help this time? How would you rewrite the query, and what would you expect the profile to
show then? A good answer compares the two profiles operator by operator, names the rows the scan
handed up in each, says what `lower` changed about where the status test could run, and predicts
the rewritten query's profile before checking it: paste either query into the panel's editor in
*Predict, then measure* and run it.

## Where to go next

- **The iterator model.** Goetz Graefe, *Volcano: An Extensible and Parallel Query Evaluation
  System*, IEEE Transactions on Knowledge and Data Engineering, 1994. The paper behind the pull
  model, and behind the shape of `Operator`.
- **Arrow's columnar format.** The [Arrow columnar format specification](https://arrow.apache.org/docs/format/Columnar.html)
  describes the arrays a batch is made of. [ch02](#batches-in-memory) takes one apart.
- **DuckDB's plans and profiles.** DuckDB's documentation on
  [`EXPLAIN ANALYZE`](https://duckdb.org/docs/guides/meta/explain_analyze) and profiling explains
  the operators and the profile's fields.
- **Another engine, built the same way.** Andy Grove's *How Query Engines Work* builds a query
  engine in Kotlin on Arrow, in its own order. It is credited here as the book that showed an
  engine could be taught by building one.
- **The scan's reader.** *[Parquet, byte by byte](https://github.com/snowch/parquet-book)*
  builds the reader your scan uses, from the file's last byte up.
