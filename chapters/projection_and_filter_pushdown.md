---
title: Projection and filter pushdown
---

(projection-and-filter-pushdown)=
# Projection and filter pushdown

## The question

How much of a file can a scan avoid reading, once it knows the columns and the predicate?

In [ch01](#the-plan-is-the-map), your scan handed every row of the file up to a filter that
threw most of them away, while DuckDB's scan tested one predicate itself. In
[ch02](#batches-in-memory), the order of the rows decided what reading them cost in memory.
Both leave the same question about the file. A scan that knows which columns a query uses and
which rows it wants can leave the rest unread. How much it leaves depends on what the file
records about itself, and on the order its rows were written in.

## Observe

The query asks for the orders of the first two weeks of March, from the file stored in date
order:

```{literalinclude} ../queries/early_march.sql
:language: sql
```

DuckDB's plan, from `EXPLAIN`:

```{include} _generated/early-march-plan.md
```

1. **The whole plan is the scan.** There is no `FILTER` and no `PROJECTION`: both date
   predicates and the choice of columns went into the scan. Handing work to the operator that
   reads the data, so the data never has to leave it, is called **pushdown**.
2. **The scan reads a column it never hands up.** `order_date` is not in the scan's
   `Projections`. The scan reads it to test the dates, then drops it.
3. **DuckDB adds `order_date IS NOT NULL`.** A null satisfies no comparison, so the added test
   changes no result. It tells the scan that a row group with nothing but nulls in the column can
   be passed over.

Now the profile of the run:

```{include} _generated/early-march-profile.md
```

The profile says the scan took in every row of the file. That is the count
[ch01](#the-plan-is-the-map) warned about: DuckDB reports the rows of the files its scan opened,
not the rows it decoded. Whether it read them all, the profile cannot say. Your own scan can,
because it counts what it reads.

A scan can avoid work in three ways, and this chapter measures each.

- **Projection pushdown** reads only the columns the query uses. Parquet stores each column of a
  row group as its own chunk of bytes, so the other chunks are never fetched.
- **Filter pushdown** tests the query's predicates inside the scan, so it hands up only the rows
  that pass.
- **Pruning** skips a row group without reading it, because the statistics the file records for
  it (each column's smallest and largest value in the row group) show that no row in it can
  satisfy the predicates.

## Predict, then measure

The same orders are in two files. `orders-sorted` holds them in date order; `orders-shuffled`
holds the same rows in a random order. Both were written with the same number of rows to a row
group:

```{include} _generated/fixtures.md
```

Your scan runs the chapter's query against each file, with the columns and both date predicates
pushed into it. Predict how many row groups it reads from each.

You have what you need. A row group can be skipped only if its range of dates, from its
smallest to its largest, lies wholly outside the query's two weeks. In the sorted file, each row
group holds a run of consecutive days. In the shuffled file, each row group's rows were drawn
from the whole year.

```lab
experiment: pruning
query: early_march.sql
```

The panel draws what your engine counted when the book was built. Its button runs the same scan
again in your browser, under Pyodide, and says whether your browser counted the same.

Compare the two files.

- **In the sorted file, the scan read only the row groups whose dates meet the query's.** Every
  other row group's range ends before the first of March or starts after the fortnight, and the
  scan skipped it without a single request for its columns.
- **In the shuffled file, the scan read every row group.** Each one's dates run from January to
  December, so each could hold a March order, and none could be ruled out. The query returned the
  same rows from both files.
- **Statistics rule out row groups, never rows.** Inside a row group it reads, the scan still
  tests every row. That is why the rows it decoded outnumber the rows it handed up, even in the
  sorted file.

## Building it

[ch01](#the-plan-is-the-map) put the engine's operators together without opening them. This
chapter opens them, starting with the shape every operator in the book shares:

```{literalinclude} ../python/query_lab/operators.py
:language: python
:start-at: class Operator:
:end-before: # A predicate the scan tests itself (ch03).
```

`batches` is a generator: ch01's pull model, in code. An operator produces a batch only when the
operator above it asks for one, and asks its child for input only then. `take` and `emit` count
every batch on its way in and out, so every operator reports the counters in COUNTERS.md without
any code of its own for counting.

### The scan

The scan is the only operator that reads. It opens the file with the Parquet reader from *Parquet,
byte by byte*, through that book's simulated object store, so every byte it reads is a request the
store logged. It reads the footer, which says where everything is, then, for each row group, the
chunks of the columns it was asked for. It decodes them and hands up one batch per row group.
Opening the file through the store, and deciding which rows of a row group to read, are methods of
their own, since later chapters grow them; the loop is the scan:

```{literalinclude} ../python/query_lab/operators.py
:language: python
:start-at: # Row group by row group:
:end-before: def open(self)
```

Called with no `filters`, as ch01's plan calls it, the scan reads every row group and hands up
every row, and a filter above it throws most of them away.

### Filter and project

A filter asks its child for a batch. It evaluates its predicate for every row with a kernel from
`pyarrow.compute`, a function that works on a whole column at once, and hands up the rows that
are true. A projection computes each output column from the batch it receives. Neither changes
how many batches flow; only the filter changes how many rows.

```{literalinclude} ../python/query_lab/operators.py
:language: python
:start-at: class Filter(Operator):
:end-before: def arrow_type(
```

```run
show: returned_unit_price.sql
```

Run ch01's plan on your edit, and you see its rows and counters. Make the filter hand up every
batch unfiltered, say: every filter's rows out become its rows in, and the plan returns every
order.

### Filters in the scan

Your scan gains one argument, `filters`: the predicates it tests itself. Each is a column
compared with a constant, the only kind of predicate a row group's smallest and largest value
can answer.

### A comparison the scan can test

A `Comparison` is used twice. Before the scan reads a row group, it asks the row group's
statistics whether any value could satisfy the comparison. The Parquet book's reader answers,
with a reason, from the chunk's minimum and maximum. After the scan reads one, it tests every
row with a kernel from `pyarrow.compute`:

```{literalinclude} ../python/query_lab/operators.py
:language: python
:start-at: class Comparison:
:end-before: def against_page(
```

### The scan, pushed down

The scan reads the columns it was asked for, and any column a filter tests. Its loop is the one
above; what changes is how it decides, row group by row group, which rows to read. If the
statistics rule the row group out, none, and no request is made for its columns. Otherwise all of
them; the loop then tests every row against the filters and hands up only the rows that pass, in
only the columns asked for:

```{literalinclude} ../python/query_lab/operators.py
:language: python
:start-at: def rows_to_read(
:end-before: def count_requests(
```

```run
experiment: pruning
query: early_march.sql
```

Make the scan read every row group, whatever its statistics say, and run the panel's report on
your edit. The rows handed up do not change; the row groups read, the bytes and the requests do.

One filter that rules a row group out is enough: the predicates are joined by `AND`, so a row
must pass them all.

### The plan

The plan is the scan, as DuckDB's is:

```{literalinclude} ../python/query_lab/plans.py
:language: python
:start-at: #: queries/early_march.sql's predicates
:end-before: def early_march_by_page(
```

The book's tests run each pushed comparison against both files and compare the rows with
DuckDB's. They check every row group the scan skipped, row by row, to make sure it held no
match, since a wrong skip loses rows where a wrong read only costs bytes.

## Compare

Your scan beside DuckDB's:

```{include} _generated/early-march-compare.md
```

- **The rows out are the same.** Both scans handed up exactly the rows the query returns.
- **The rows in are not.** Yours reports the rows it decoded, from the row groups it read.
  DuckDB's reports every row of the file, whatever it skipped.

DuckDB does not report the bytes it reads, so the book counts them outside it, at the file
system DuckDB reads through. Here is the chapter's query, on both files, with less and then more
pushed into your scan, and then DuckDB's:

```{include} _generated/early-march-pushdown.md
```

- **Projection pushdown cuts the bytes, and nothing else.** With only the query's columns pushed,
  your scan fetched a fraction of the file, but still decoded every row and handed all of them
  up.
- **Filter pushdown cuts the rows handed up on both files, and the bytes only on the sorted
  one.** The shuffled file's statistics could rule out nothing, so its scan read what it read
  with the columns alone.
- **DuckDB read exactly the bytes your scan read.** Both read the footer and the same column
  chunks of the same row groups: the same decisions, from the same statistics.
- **The shuffled file costs more to read, even for the same columns.** In date order, a row
  group's dates are long runs of the same day, which Parquet's encodings store in few bytes.
  Shuffled, they are not. The order the rows were written in changes the size of what a scan
  must fetch, before any row is skipped.

## What this cannot tell you

- **How long the reads took.** The counters give bytes and requests. On object storage, each
  request costs a wait before its first byte arrives, so fewer requests matter as much as fewer
  bytes. *Parquet, byte by byte* models that; this book counts the requests.
- **Anything finer than a row group.** Your scan decides once per row group. A Parquet file can
  also carry a page index and Bloom filters, which let a reader skip pages inside a row group or
  rule out one exact value. The Parquet book's reader uses them; your scan does not yet, and
  Part II returns to them.
- **Predicates that are not a column against a constant.** Statistics cannot answer
  `amount / quantity > 100` or `lower(status) = 'returned'`: the first compares two columns, and
  the second changes the column before it compares it. Both wait for a filter above the scan.
- **Tables of many files.** A table is often many files, each with statistics of its own, and a
  table format can record them all in one place, so whole files are skipped unopened. Part II
  returns to that too.
- **How DuckDB decides.** The comparison is of bytes read, not of DuckDB's code. It shows that
  both engines skipped the same row groups, not how DuckDB chose them.

## What this means for your design

- **Sort a file on the column you filter by most.** The same rows, sorted by date, let the scan
  skip most of the file for a fortnight's orders. Shuffled, it skipped none of it. A file written
  in arrival order is often close to sorted by time already, which is why date filters prune well
  in practice.
- **Write predicates as a column against a constant.** `order_date >= DATE '2024-03-01'` can be
  pushed into the scan and answered by statistics. The same test hidden inside an expression
  cannot, and every row reaches a filter.
- **Select only the columns you need.** Projection pushdown needs nothing from the data's order,
  and saves bytes on every file.
- **Row group size sets how finely a scan can skip.** A row group holding fewer rows covers a
  narrower range of a sorted column, so fewer rows are read that the query does not want. It also
  adds column chunks, and requests, for every column the query reads.

## Key takeaways

:::{div}
:class: takeaways

- **Pushdown hands work to the scan.** DuckDB's whole plan for the query was one scan: it chose
  the columns and tested the dates as it read.
- **Projection pushdown saves bytes on any file.** Parquet stores each column apart, so a column
  nobody asks for is never fetched.
- **Pruning needs statistics that can rule a row group out.** A row group's smallest and largest
  value must lie outside the predicate's range, and in the sorted file most did.
- **The order of the rows decides what pruning can do.** Shuffled, every row group spanned the
  year, and the scan read everything to hand up the same rows.
- **A profile's rows in is not rows read.** DuckDB reported every row as scanned while it read
  the bytes your scan read, which is a small part of the file.
:::

## Problems

There are four problems. The first three are code with tests; the fourth is a slow query to
diagnose, with no test. Write your answers to the first three in the workbench, and run the
graders there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: projection_and_filter_pushdown
```

**3.1 Could it match?** Write `could_match`: given a comparison and a row group's smallest and
largest value, whether any value between them could satisfy it. The graders try every
whole-number range in a small window and every constant around it, check the real files' row
groups so that no row group holding a match is ruled out, and check that you rule out every row
group the book's scan skips. Mind `!=`, which rules out only a row group whose every value is
the constant.

**3.2 Push the status test.** Write `returned_unit_price_pushed`: ch01's plan for the returned
orders, with `status = 'returned'` tested inside the scan, as DuckDB tests it. The graders
compare your rows with DuckDB's, check that your scan handed up exactly the rows DuckDB's scan
did, and check that it hands up no `status` column and that the unit price is the only test left
to a filter. Before you run it, predict how many row groups your scan will skip, from the status
counts in the fixtures' recipe in [ch01](#the-plan-is-the-map).

**3.3 A limit.** Write `Limit`: an operator that hands up the first `n` rows its child produces,
and no more. It must stop asking its child for batches as soon as it has `n` rows. The graders
compare its rows with DuckDB's `LIMIT`, and count the batches its child produced, with and without
a filter between them. A limit that drains its child fails even when its rows are right. This is
the pull model reading less: a limit at the top of a plan stops the scan at the bottom.

**3.4 Diagnose the slow query.** No test. A colleague looks for the year's largest orders:

```{literalinclude} ../queries/largest_orders.sql
:language: sql
```

It returns few rows, and your scan, with the predicate pushed into it, read this:

```{include} _generated/largest-orders-row-groups.md
```

Why did pruning skip nothing, when so few orders match? What would you change so a query like
this reads less, and what would each change cost the chapter's date query? A good answer says
what every row group's range of `amount` has in common and why, names what the file would need
to record or how it would need to be ordered for the scan to skip, and predicts the row groups
read after each change.

## Where to go next

- **Skipping data, in depth.** *[Parquet, byte by byte](https://github.com/snowch/parquet-book)*
  builds the statistics, the page index and the Bloom filters your scan's decision comes from, in
  its chapters on metadata and statistics, skipping data, and how readers read.
- **The format's own account.** The [Parquet format documentation](https://parquet.apache.org/docs/file-format/)
  describes where statistics sit in a file's metadata and what a reader may conclude from them.
- **Where the idea comes from.** Guido Moerkotte, *Small Materialized Aggregates: A Light Weight
  Index Structure for Data Warehousing*, VLDB 1998. A minimum and maximum kept for each block of
  rows, so a query can skip blocks: the idea behind every engine's row group statistics.
- **DuckDB's Parquet reader.** DuckDB's [Parquet documentation](https://duckdb.org/docs/data/parquet/overview)
  describes the projection and filter pushdown its scan does.
