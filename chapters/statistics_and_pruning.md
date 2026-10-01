---
title: Statistics and pruning
---

(statistics-and-pruning)=
# Statistics and pruning

## The question

How finely can a scan skip, and what does skipping finely cost?

In [ch03](#projection-and-filter-pushdown), your scan skipped whole row groups, and only where a
row group's smallest and largest date ruled it out. That made the file's order decisive. It also
made the file's cut decisive, which the chapter did not test: a row group is the smallest thing
those statistics describe, so a scan can skip no finer than the row groups the writer chose. This
chapter cuts the same orders differently, and asks what a scan can skip inside a row group.

## Observe

The query is chapter 3's fortnight of orders, from a new file, `orders-paged`. It holds the same
orders in the same date order, written as one row group instead of ten:

```{literalinclude} ../queries/early_march_paged.sql
:language: sql
```

DuckDB plans it as it planned chapter 3's query: one scan, with the columns and the dates pushed
into it.

```{include} _generated/early-march-paged-plan.md
```

The plan is the same; what DuckDB reads is not. Counted at the file system, as in
[ch03](#projection-and-filter-pushdown):

```{include} _generated/grain.md
```

1. **From the paged file, the fortnight costs DuckDB as much as every row.** Its one row group's
   dates run from January to December, so the row group's statistics cannot rule it out, and
   DuckDB reads the whole of every column the query uses.
2. **The paged file is not short of statistics.** Inside a row group, Parquet stores each column
   in **data pages** of a few thousand values or fewer, and a writer can record the smallest and
   largest value of every page. The paged file carries these for every column. DuckDB, in the
   pinned version, does not use them.

The per-page statistics sit in two structures a writer can add after a row group's data. The
**column index** holds each page's smallest and largest value; the **offset index** holds where
each page starts in the file and the first row it holds. Together they are the file's **page
index**: statistics for each page, and the addresses to fetch one page alone.

## Predict, then measure

Your scan can now read the page index. For each row group it cannot rule out, it looks up the
pages of each filtered column and keeps those whose range might hold a match. Then it fetches, for
every column it reads, only the pages holding the kept rows.

Predict what it reads of each file. From `orders-sorted`, reading by row group as in
[ch03](#projection-and-filter-pushdown), how many of its row groups? From `orders-paged`, reading
by page, how many of the date column's pages? The grain table above says how many of each the
files have, and both files hold the year's orders in date order, so a unit covers a run of
consecutive days.

```lab
experiment: pruning
query: early_march_paged.sql
fixtures: orders-sorted.parquet, orders-paged.parquet
```

The panel draws what your engine counted when the book was built. Its button runs the same scans
again in your browser.

- **Pages cut the year finer than row groups.** A page of the paged file holds a few weeks of
  orders, where a row group of the sorted file held about five. The fortnight falls inside one or
  two pages, and the scan decoded only their rows.
- **Finer skipping reads fewer bytes, in more requests.** The scan fetched each kept page on its
  own, and the page index before it, so its requests went up as its bytes came down. On object
  storage each request waits before its first byte arrives, so the finer cut is not free.

## Building it

### A page's bounds

A comparison already knew how to test a row group's statistics. Testing a page is the same
question, asked of the column index's bounds for one page:

```{literalinclude} ../python/query_lab/operators.py
:language: python
:start-at: def against_page(
:end-before: def against_bounds(self, comparator
```

### The rows worth reading

For each filter, the scan fetches that column's column index and offset index, and keeps the rows
of the pages that might match. A row must pass every filter, so the scan reads a row only if every
filter kept its page:

```{literalinclude} ../python/query_lab/operators.py
:language: python
:start-at: def pages_kept(
:end-before: def read(self, leaf
```

```run
experiment: pruning
query: early_march_paged.sql
fixtures: orders-sorted.parquet, orders-paged.parquet
```

Keep every page, and run the panel's report on your edit: the paged file now costs a little more
than DuckDB paid, because the scan still reads the page index, and uses none of it.

### Only those pages

Each column's pages end at different rows: a page holds a number of bytes, not rows, and columns
of different widths fill their pages at different rates. So each column finds its own pages that
hold the kept rows, fetches them and nothing else, and decodes them. A column encoded with a
dictionary also needs its **dictionary page**, which every one of its data pages refers to:

```{literalinclude} ../python/query_lab/operators.py
:language: python
:start-at: def read(self, leaf
:end-before: def schema(self) -> pa.Schema:
```

### The plan

The plan is chapter 3's scan, told to use the page index. On a file with no page index, it reads
by row group, exactly as chapter 3's did:

```{literalinclude} ../python/query_lab/plans.py
:language: python
:start-at: def early_march_by_page(
:end-before: def early_march_table(
```

The book's tests run the scan by page with several predicates and compare its rows with DuckDB's.
They check every row of the file that matches, to make sure it lay in a page the scan kept, and
check that on a file without a page index the scan reads exactly what chapter 3's did.

## Compare

Your scan beside DuckDB's, on the paged file:

```{include} _generated/early-march-paged-compare.md
```

- **All three hand up the same rows.** The page index changes what is read, never what is
  returned.
- **By row group, your scan reads exactly what DuckDB reads.** Both fetch the whole of each
  column the query uses, because the one row group's statistics cannot rule it out.
- **By page, your scan reads a fraction of it.** It decodes the rows of the pages that might hold
  the fortnight, and fetches nothing else but the page index and the small dictionaries.
- **DuckDB does not report what its scan decoded.** Its bytes, counted outside it, are the
  evidence that it read the whole row group.

What the scan skips, it never decodes. Time your scan of the early March orders three ways, the
filter pushed into it each time: from the shuffled file, whose statistics rule out nothing; from
the sorted file, whose row groups' bounds rule out most of it; and from the paged file, by page:

```timed
of: pruning
```

- **Sorting the file decides what the filter can save.** The same scan, the same
  filter, the same rows out: the shuffled file makes it decode every row group, and the sorted
  file only those whose dates might match.
- **The page index takes the same idea a level down.** By page, the scan decodes the pages that
  might hold the fortnight, and is quicker again, here, where a request costs nothing to wait
  for.

## What this cannot tell you

- **How long the requests take from object storage.** Reading by page made more, smaller
  requests. The timing above reads from memory, where a request waits for nothing; whether
  reading by page is faster from storage depends on how long each request waits, which neither
  the counters nor that timing say. *Parquet, byte by
  byte* models it, and coalesces nearby pages into one request to trade bytes for requests.
- **Bloom filters.** A writer can also add a Bloom filter per column chunk, which can rule out one
  exact value that lies between the minimum and maximum. Your scan does not read them.
- **Any version of DuckDB but the pinned one.** The comparison shows what DuckDB 1.1.2 reads for
  this file, not what other versions do.
- **How the writer chose its pages.** The paged file's pages were cut by a writer aiming at a size
  in bytes. Another writer, or other settings, would cut them elsewhere, and the scan would skip
  differently.

## What this means for your design

- **Choose row groups for the reads, and pages for the skipping.** Large row groups keep requests
  few and columns long; a page index lets a reader skip inside them. Write the page index where
  your readers use it, and check that they do: the pinned DuckDB does not.
- **Sort by what you filter on.** A page's bounds are as useful as a row group's only when the
  rows in it are alike. The paged file skips well because it is sorted by date.
- **Keep dictionaries for columns with few distinct values.** A dictionary page is read with any
  page of its column, so a column of nearly unique values, encoded with a dictionary, costs most of
  its bytes however few pages are kept. Problem 4.3 measures it.
- **Mind the requests.** A scan that fetches pages one by one trades bytes for requests. On object
  storage, a reader should fetch neighbouring pages together.

## Key takeaways

:::{div}
:class: takeaways

- **A scan skips no finer than the statistics it reads.** Row group statistics skip row groups; a
  page index skips pages.
- **The same rows, cut differently, cost different bytes.** One row group with no usable
  statistics made DuckDB read every column in full for a fortnight.
- **The page index is the column index and the offset index.** One says what each page holds, the
  other where it is and which rows it covers.
- **Every column finds its own pages.** Pages end at different rows in different columns, so the
  kept rows map to different pages in each.
- **Finer skipping costs requests.** Fewer bytes came in more pieces.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: statistics_and_pruning
```

**4.1 Which pages?** Write `pages_for`: given the rows a scan kept and one column's pages, the
pages that hold any kept row. The graders try many random cuts of rows and pages, and every
column of the paged file with the chapter's fortnight.

**4.2 Kept rows.** Write `kept_rows`: given one column's page bounds and several comparisons on
it, the rows worth reading. Keep a page only if a single value in its range could pass every
comparison at once, which is tighter than the book's scan: that keeps a page if each comparison
alone could pass. The graders try every whole number in small ranges, and check the paged file's
dates so that no page holding a match is dropped.

**4.3 Diagnose the slow query.** No test. A colleague writes the paged file with the writer's
default settings, which give every column a dictionary, and runs the chapter's query by page on
both copies:

```{include} _generated/dictionary-pages.md
```

The scan decoded the same rows from both. Why did it read so many more bytes from the default
copy, and which columns are to blame? What does a dictionary page hold for a column like
`order_id`, and why must every page of that column be read with it? What would you tell the
colleague to change? A good answer names the columns, explains why a column of nearly unique values
gains nothing from a dictionary, and predicts what the scan would read once they changed it.

## Where to go next

- **The page index, byte by byte.** *[Parquet, byte by byte](https://github.com/snowch/parquet-book)*
  decodes the column index and the offset index, and the Bloom filter, in its chapters on skipping
  data and on how readers read. Your scan's page decisions are its reader's.
- **The format's own account.** The [Parquet page index specification](https://parquet.apache.org/docs/file-format/pageindex/)
  describes the column index and the offset index, and why they sit apart from the data.
- **Where the idea comes from.** Guido Moerkotte, *Small Materialized Aggregates: A Light Weight
  Index Structure for Data Warehousing*, VLDB 1998. The same minimum and maximum, kept for smaller
  blocks.
- **DuckDB's Parquet reader.** DuckDB's [Parquet documentation](https://duckdb.org/docs/data/parquet/overview)
  describes what its reader pushes into the scan, and the settings that change it.
