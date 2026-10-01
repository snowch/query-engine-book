---
title: The plan is the map
---

(the-plan-is-the-map)=
# The plan is the map

## The question

What does an engine do with your query, and where can you see what each step costs?

A query engine is a machine for moving and transforming data. You hand it a sentence of SQL, and
it reads data from storage, passes it from one step to the next, holds some of it and computes
with it, until the rows you asked for come out. Three questions describe what it did, and each has
its own answer:

| The question | What answers it |
|---|---|
| What does the query mean? | A **logical plan**: the steps the SQL asks for, such as *read the orders*, *keep the returned ones*, *compute a unit price*, with nothing yet decided about how. [ch11](#from-sql-to-a-logical-plan) builds one. |
| How will the engine run it? | The **physical plan**: the operators the engine chose to do those steps. `EXPLAIN` prints it. |
| What did running it do? | The **profile**: the same operators, each with what it counted as it ran. |

**The plan is the map, and the profile is the journey.** The plan says where the data is meant to
go; the profile says how much of it went through each part of the map. This chapter reads both for
one query, then builds the same plan and checks it against them.

Engines count many things, and a query costs more than any one table can hold: processor time,
requests to storage, decompression, waiting for other threads. Four kinds of cost recur throughout
this book, and the rest of it measures each:

| What a query pays | The question it asks | Where the book measures it |
|---|---|---|
| Bytes read | How much did the engine fetch from storage? | [Part II](#part-reading-less) |
| Rows moved | How many rows passed from one step to the next? | This chapter, and every one after |
| Memory held | How much did a step hold at once? | [Part III](#part-computing) |
| Rows sent between machines | How much crossed from one machine to another? | [Part V](#part-scaling-out) |

They are the book's way of looking at a query, not a complete list. Every design choice in the book
makes an engine read less, move less, hold less or send less, and every chapter measures which.

## Observe

The first query asks for the returned orders. It reads `orders-sorted`, one of the book's
fixtures: a year of orders, one row each, written by a real Parquet writer from a seeded
generator. The query is a file in the repository, and this page quotes it, so the SQL you read is
the SQL every figure below ran.

```{literalinclude} ../queries/returned_orders.sql
:language: sql
```

Every query the book quotes can be changed and run in your browser: press **Edit and run** above
it. Your version runs under DuckDB in the page, and draws its plan and its first rows.

Ask DuckDB how it will run a query, without running it, by putting `EXPLAIN` in front. What comes
back is the physical plan, drawn as DuckDB draws it in a terminal:

```{include} _generated/returned-orders-explain.md
```

DuckDB draws a plan with the first operator to touch the data at the bottom and the result at the
top, and the rows travel upwards. The whole plan is one box. Each box is an **operator**: one job,
with one input and one output.
This one is a **scan**, the operator that reads rows from storage, and it does three things at
once. It reads only the columns the query names, its `Projections`. It tests each row's status as
it reads it, its `Filters`. And it hands up only the rows that pass. The status test is a
**predicate**: a condition, such as `status = 'returned'`, that each row either meets or does
not. **An operator describes a job, not a separate piece of code**: reading, testing and dropping
rows are all the scan's work here. The last line of the box is the operator's **cardinality
estimate**: how many rows the planner, the part of the engine that turned the SQL into this plan,
expects it to produce. It was made before a single row was read.

Now ask for the returned orders whose unit price was over a threshold:

```{literalinclude} ../queries/returned_unit_price.sql
:language: sql
```

```{include} _generated/returned-unit-price-explain.md
```

The plan grew two operators. The new predicate divides one column by another, and a scan tests
only a column against a constant, so the price test gets an operator of its own: a **filter**,
which keeps the rows for which a predicate is true. The unit price is computed, not read, so a
**projection** computes the columns the query returns from the columns it is given. The status
test stayed in the scan.

**Read a plan from the bottom up, the way the rows travel.** The scan at the bottom hands up the
returned orders, the filter above it keeps the dear ones, and the projection at the top computes
their unit price. The top of the plan is where the rows end up, not where the work starts.

A plan tells you what the engine intends. To see what it did, you run the query with profiling on,
and DuckDB writes the profile: the same operators, each with the rows it took in and handed out.
The book runs every query this way, through one function in `query_lab.reference`, and the next
section sets the profile beside the plan.

## Predict, then measure

In the chapters that follow, you predict what an operator will do before you measure it. Here
the prediction is the planner's: `EXPLAIN` printed an estimate for each operator before the
query ran, and running the query measures what each operator did. The panel sets the two side by
side, operator by operator. DuckDB calls the scan `PARQUET_SCAN` in the plan and
`TABLE_SCAN` in the profile: two names for the same operator, not two operators.

Above the plan are two changes to try: a higher price threshold, and shipped orders in place of
returned ones. Before you press either, look at the plan and decide which of its operators each
change reaches, and whether it will move their estimates, their measurements, or both. Each
change redraws the plan at once, from a run the book made when it was built.

```lab
experiment: plan
query: returned_unit_price.sql
variants: pricier_returns.sql, shipped_unit_price.sql
```

The panel draws what DuckDB measured when the book was built. Its button runs the same report
again in your browser, and says whether your browser's DuckDB gave the same answer.

Now press them, and check your answers.

- **A change reaches only the operator that runs the test it alters, and those above it.** The
  price test runs in the `FILTER`, so a higher threshold leaves the scan's rows as they were and
  changes the filter's and the projection's. The status test runs inside the scan, so asking for
  shipped orders changes the rows of every operator.
- **The measurements move, and the estimates do not.** Whichever orders you ask for, the planner
  expects the same rows from the scan and the same rows from the filter. It knows how many rows
  the file holds, and nothing about how `status` or the unit price are spread across them. So it
  gives every predicate the same default **selectivity**, the fraction of rows a predicate keeps.
- **An estimate can be wrong in either direction.** For the returned orders it is too high; for
  the shipped ones it is far too low. A planner that chooses between plans with guesses like
  these can choose the wrong one.
- **Rows in, for each operator above the scan, is the output of the operator below.** Nothing is
  lost between operators. That makes the profile a ledger: each operator's reduction is its rows
  out against its rows in.
- **Rows in, for the scan, is every row in the file.** That is DuckDB's report of the rows in the
  files it opened. [ch03](#projection-and-filter-pushdown) shows that it stays the same when the
  scan skips most of the file, so it tells you what the scan was responsible for, not what it
  decoded.

**A query engine plans with predictions and runs on what is there.** The distance between the two
is where a planner earns its keep, and [Part IV](#part-planning) is about narrowing it.

The profile, read as a journey from the file to the result:

```{include} _generated/returned-unit-price-journey.md
```

That is the book in miniature. Every later chapter asks what happened to a flow of rows like this
one, and what each step of it cost.

**The measurements are predictable because you know how the fixture was generated. The planner
does not: it has to estimate from what the file tells it.** For the curious, the generator's
recipe:

```{include} _generated/orders-recipe.md
```

Problem 1.2 asks you to work the measurements out from it;
[ch13](#statistics-cost-and-join-order) gives a planner part of the same knowledge, from what a
file says about itself.

Keep the book's three measurements. When you build the same plan in the next section, your
operators report the same counters, and they must agree with these.

## Building it

Your engine runs the same plan, from the same kinds of operator. They are ready-made parts: you
put them together here, and each one's own code is the subject of the chapter that measures it,
starting with [ch03](#projection-and-filter-pushdown). What you need to know about them is how
they hand rows to each other.

Each operator produces a stream of **batches**. A batch is a slice of a table, a few thousand rows
held column by column as Apache Arrow arrays, so an operator works on a column at a time instead
of a row at a time. An operator produces a batch only when the operator above it asks for one,
and asks the operator below it, its child, for input only then. So the operator at the top drives
the run, and nothing is read until something above asks. This is the **pull model**: rows are
pulled up the plan, not pushed. Every operator counts the batches and rows it takes in and hands
out, the counters in COUNTERS.md.

The scan is the only operator that reads. A Parquet file is cut into **row groups**: horizontal
slices of the table, each holding every column's values for a run of rows. The scan reads the
columns it is asked for from each row group and decodes them into Arrow arrays, one batch per row
group. The reader underneath it comes from this book's companion, which takes the file's layout
apart; this book needs only the row groups. A filter evaluates its predicate on each batch and
hands up the rows that are true; a projection computes each output column from the batch it
receives.

### The plan

The engine has no planner yet, so you write the plan by hand, bottom up, the way `EXPLAIN` drew
DuckDB's. The plan's module imports Arrow's Python library, pyarrow, as `pa`, and its compute
functions, the kernels an operator runs on a whole column at once, as `pc`:

```{literalinclude} ../python/query_lab/plans.py
:language: python
:start-at: import pyarrow as pa
:end-before: import pyarrow.parquet as pq
```

`Scan`, `Filter` and `Project` are the engine's operators, from `query_lab.operators`. The scan
reads the five columns the query uses. Two filters take the two predicates in turn, and a
projection computes the unit price:

```{literalinclude} ../python/query_lab/plans.py
:language: python
:start-at: def returned_unit_price(
:end-before: def in_date_order(
```

```run
show: returned_unit_price.sql
```

Press **Edit and run** on a listing like this one to change it and run it in your browser, as you
would a notebook cell: the plan runs, and you see the first rows it returned and what each
operator counted. Skip the filter on the status, say, by handing the price filter `scan` in place
of `returned`: more rows come back, and the price filter takes in every row of the file. Edit, run,
look, and edit again. The book's own code comes back when you close the editor, and nothing you
change moves a number the chapter prints.

Called with no `filters`, as this plan calls it, the scan reads every row group and hands up
every row. It tests no predicate, where DuckDB's did. That difference is the first thing the
comparison below shows, and [ch03](#projection-and-filter-pushdown) closes it. The book's tests run
this plan every time the book is built. They check that its counters obey COUNTERS.md's rules,
and compare its result with DuckDB's, row for row.

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

**The same logical work does not mean the same physical work.** Your plan and DuckDB's do the same
jobs and hand up the same rows; DuckDB's does one of the jobs inside its scan, where yours gives it
an operator of its own, and pays for it in rows moved.

So the next question is not how fast a query runs. It is **how much work the engine can avoid doing
in the first place**: which columns, row groups and rows it need never read or hand up. That is
[Part II](#part-reading-less)'s question, from [ch03](#projection-and-filter-pushdown). First,
[ch02](#batches-in-memory) opens the batches the rows travel in, to see what moving one costs.

## What this cannot tell you

- **How long anything took.** The counters say how much work each operator did, not how fast.
  In the page, both engines run inside your browser: yours as Python under Pyodide, DuckDB as its
  C++ compiled to WebAssembly. Each is slower there than on a server, by an amount that depends
  on your browser and your machine, and your engine decodes Parquet in Python besides, many times
  slower than DuckDB's C++ anywhere. A time would measure all of that, not the design. The
  counters come out the same in your browser as when the book was built. The chapters that are
  about time use small simulators; the book never prints a time.
- **What DuckDB's scan decoded.** DuckDB reports the rows in the files its scan opened, not the
  rows it decoded. [ch03](#projection-and-filter-pushdown) counts that with your own scan.
- **Anything about statistics.** Your scan, as this chapter uses it, reads every row group,
  whatever the query asks. It ignores the minimum and maximum the file records for each column.
- **Memory beyond Arrow's buffers.** Peak memory counts the Arrow buffers an operator holds. The
  reader decodes each column into Python values before your scan builds its arrays, and those
  are not counted.
- **Plans with more than one input, or more rows than memory.** One file, one thread, and every
  batch small. Joins, running out of memory, and parallelism are later parts of the book.
- **How a planner chooses.** You wrote this plan. The planner that writes plans, and the
  statistics it guesses with, are Part IV.

## What this means for your design

Read any plan in five steps, and each step points at a part of the book:

1. **Start at the bottom, at the scan.** What enters the engine: which files, which columns,
   which rows?
2. **Move up.** Where are rows dropped, computed or combined?
3. **Compare the estimates with the measurements.** Where did the planner guess wrong, and did it
   matter? ([Part IV](#part-planning))
4. **Ask what could have been avoided.** Could the scan have read fewer columns, fewer row groups,
   fewer rows? ([Part II](#part-reading-less))
5. **Ask what the rest cost.** What did each step compute and hold, and would it have to be sent
   between machines? ([Part III](#part-computing), [Part V](#part-scaling-out))

Then:

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

- **The plan is the map; the profile is the journey.** The physical plan names each operator; the
  profile says how many rows each took in and handed out.
- **An operator is a job, not a piece of code.** DuckDB's scan read, tested and dropped rows in
  one operator; a predicate it cannot test there gets a filter of its own.
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

**1.1 A plan of your own.** Write `customer_orders`, the plan for every order of one customer:
`order_id`, `order_date` and `amount`, where `customer_id` equals the customer given. Build it
from the book's operators, as the chapter built its plan. The graders compare its result with
DuckDB's for several customers, check its counters obey the rules, and check the scan reads no
column the query does not use.

**1.2 Work it out from the recipe.** Write `expected_rows`: from the orders' recipe above, the
rows the chapter's query keeps, for any status and any price threshold. The graders compare your
answer with DuckDB's count for several of each. It is the estimate the planner could not make,
because nobody gave it the recipe.

**1.3 Find where the filtering stopped happening early.** No test. A colleague finds the same
returned orders with this query:

```{literalinclude} ../queries/lower_status.sql
:language: sql
```

It returns the same rows as the chapter's query. DuckDB plans it like this; set it beside the
chapter's plan in *Observe*:

```{include} _generated/lower-status-explain.md
```

And DuckDB profiles it like this:

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
