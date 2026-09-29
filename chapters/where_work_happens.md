---
title: Where work happens
---

(where-work-happens)=
# Where work happens

## The question

When a table is many files, what decides which of them are opened, and where are the rows tested?

In [ch03](#projection-and-filter-pushdown) and [ch04](#statistics-and-pruning), your scan skipped
row groups and pages inside one file. Before it could skip anything, it had to open the file and
read its footer, because the statistics it skipped by live there. A table in a data lake is
rarely one file. It is hundreds or thousands, and a scan that must open each one to learn what it
holds pays for every footer before it reads a row. There is a second cost the earlier chapters
took for granted: every byte your scan tested had already crossed from the storage to the
engine. This chapter moves both decisions. It decides which files to open before opening any,
and then asks what changes when the storage tests the rows itself.

## Observe

The table is `orders-by-month`: the sorted orders of [ch03](#projection-and-filter-pushdown),
cut into one file per month. Each file sits in a directory named for its month, such as
`month=2024-03`. The query is chapter 3's fortnight, asked of every file in the table through a
glob:

```{literalinclude} ../queries/early_march_table.sql
:language: sql
```

DuckDB's plan is one scan, with the columns and the dates pushed into it, as it was for one file:

```{include} _generated/early-march-table-plan.md
```

The plan does not say how many files the scan will open. Now the same fortnight, asked of the
directories' names instead of the dates alone:

```{literalinclude} ../queries/early_march_partition.sql
:language: sql
```

```{include} _generated/early-march-partition-plan.md
```

1. **The second plan filters files, not rows.** Naming each directory for the value of a column,
   `month=2024-03`, is **Hive partitioning**, after the Hadoop warehouse that made it common.
   The `month` column is in no file. DuckDB reads it from each file's path, so the test
   `month = '2024-03'` rules a file out from its name alone, and the plan says how many files are
   left to scan.
2. **The first plan cannot do that.** Its dates are inside the files. To learn a file's dates,
   DuckDB must open it and read its footer, where the row group statistics are.
3. **The query had to change to use the layout.** The month and the dates say the same thing
   twice, and a query that asks only for the dates gains nothing from the directories.

A table format does better than directory names. It keeps, beside the data files, a
**table metadata** file: a list of the table's data files, each with the smallest and largest
value of every column in it. Apache Iceberg keeps this in its manifests, and Delta Lake in its
transaction log. A reader of the table metadata can rule out a file by any column, from one read,
without opening the file.

## Predict, then measure

Your engine gains a table scan. By its metadata, it reads the table metadata first and opens only
the files whose bounds might hold a match. By its files, it lists the table's directory and opens
every file, as DuckDB's glob does, and skips a file's row groups by the statistics in its footer.

Predict how many files each scan opens. The table holds the year's orders in date order, a month
to a file, and the query asks for a fortnight.

```lab
experiment: pruning
query: early_march_table.sql
scans: by its metadata, by its files
```

The panel draws what your engine counted when the book was built. Its button runs the same scans
again in your browser.

- **By its metadata, the scan opens one file.** The bounds of every other month rule it out, and
  the scan never fetches a byte of it.
- **By its files, the scan opens every file.** Each file's footer rules out its one row group, so
  the scan decodes the same rows; but to read a footer, the scan must first ask where it is, then
  fetch it. Every file costs requests before the scan knows it holds nothing.

## Building it

### A file's bounds, before it is opened

The table metadata stores each file's bounds as a Parquet file's statistics store them: the
smallest and largest value, encoded as the column's values are, with the comparator that orders
them. So a comparison can hand them to the Parquet book's reader, which decides for a file as it
decides for a row group:

```{literalinclude} ../python/query_lab/operators.py
:language: python
:start-at: def against_bounds(self, comparator
:end-before: #: The kernel that tests each row
```

### The table scan

The table scan reads the table metadata, or lists the directory, then opens the files it could
not rule out, one after another. Each file it opens is read by chapter 4's scan, with the same
filters, so everything the earlier chapters built still applies inside each file. All the files
share one store, so the table's counters are every request the scan made:

```{literalinclude} ../python/query_lab/operators.py
:language: python
:start-at: class TableScan(Operator):
:end-before: def count_requests(
```

```run
experiment: pruning
query: early_march_table.sql
scans: by its metadata, by its files
```

Make `ruled_out` rule out nothing, and run the panel's report: the scan by the metadata now opens
every file, and pays for the metadata as well.

### The plan

```{literalinclude} ../python/query_lab/plans.py
:language: python
:start-at: def early_march_table(
:end-before: def early_march_in_storage(
```

The book's tests run the table scan with several predicates, both ways, and compare its rows with
DuckDB's. They read every file the metadata ruled out, row by row, to make sure it held no match,
and check that the metadata lists every file with its true row count and size.

### Storage that tests the rows

Every scan so far fetched bytes from the storage and tested the rows in the engine. An object
store answers ranges of bytes and nothing more, so an engine reading from one has no other
choice. Some storage can do more. Given a file, the columns and the filters, it scans the file
where the file lives and sends back only the rows that pass. Vast DataBase, for example, takes a
query's columns and predicates in its client's request, evaluates the predicates next to its
disks, and returns the matching rows as Arrow batches.

Your engine can simulate such storage with the scan it already has, run on the storage's side.
The storage sends the rows as an **Arrow IPC** stream, the format Arrow uses to move batches
between processes, and the engine's scan makes one request and reads what comes back:

```{literalinclude} ../python/query_lab/storage.py
:language: python
:start-at: class ComputingStore:
```

The engine counts what crossed the network; the storage keeps its own scan's counters, which say
what it read from its disks. The two are reported side by side and never added. Here is chapter
3's fortnight, from the sorted and the shuffled file, tested in your engine and in the storage:

```{include} _generated/storage.md
```

- **The storage sends the result, not the data.** The rows that pass are a small share of what
  the scan read, so far fewer bytes crossed the network, in one request.
- **The storage still reads what the scan read.** Moving the test changed where the bytes were
  read, not how many. On the shuffled file, the storage read every row group, as your engine did
  in [ch03](#projection-and-filter-pushdown).
- **The order of the rows stops mattering to the network.** Both files send about the same bytes,
  because both hold the same matching rows. It still matters to the storage's disks.

## Compare

Your table scans beside DuckDB's, on the same table:

```{include} _generated/early-march-table-compare.md
```

- **All four hand up the same rows.** Which files a scan opens changes what it reads, never what
  it returns.
- **By its files, your scan reads exactly what DuckDB's glob reads.** Both open every file, read
  each footer, and read the row group of March alone.
- **The table metadata saves requests more than bytes.** One file opened instead of every file
  cut the requests most. The metadata is not free: it holds the bounds of every column of every
  file, and on a table this small it is a large share of what the scan read. On a table of
  thousands of files, it is one read against thousands of footers.
- **By the month in the path, DuckDB reads the fewest bytes.** A path costs nothing to read. It
  opened one file besides March's; from the bytes, it read that file's footer, which it seems to
  use for the table's schema. Its plan does not say.

## What this cannot tell you

- **How long listing takes.** The simulated store lists a directory in one request. A real object
  store returns its keys a page at a time, a request per page, and a table of many directories
  lists slowly. Table metadata avoids listing altogether.
- **What a real table format stores.** Iceberg's metadata is a tree: a metadata file names a
  snapshot, whose manifest list names manifests, which list the data files with their bounds. The
  book's table metadata is one file with the same bounds, and none of the snapshots, schema
  history or deletes that make a table format a format.
- **What the storage's work costs.** The storage that tests rows decoded as many rows as your
  engine would have. The counters say where the bytes moved, not how busy the storage was, or
  whether it shares its processors with other queries.
- **Any version of DuckDB but the pinned one.** The comparison shows what DuckDB 1.1.2 opens and
  reads for this table.

## What this means for your design

- **Lay a table out by what its queries filter on.** Files cut by month let a query by date skip
  most of them. A query by customer gains nothing from the same files, as problem 5.3 shows.
- **Keep table metadata with column bounds.** A reader of it rules files out by any column, from
  one read, without opening them. It saves most where the files are many.
- **Beware many small files.** Each file a scan opens costs requests for its footer before it
  yields a row, and the bounds of a small file are often as wide as a large one's.
- **Filter in the storage when the network is the constraint.** Storage that tests rows sends
  the result instead of the data, which helps most when the predicate is selective. It does not
  help the storage's own disks: a badly laid out file still costs a full read, only somewhere
  else.

## Key takeaways

:::{div}
:class: takeaways

- **A file's statistics cost a request to read.** Without table metadata, a scan opens every file
  to learn what it holds, even the files it then skips.
- **Table metadata moves the decision before the open.** A list of files with their bounds lets a
  scan rule out a file it never touches.
- **Hive partitioning works only for the query that names the partition column.** The directory's
  name is free to read, but the query must ask for it.
- **Where the rows are tested decides what crosses the network.** Tested in the storage, only the
  result travels; tested in the engine, everything the scan read does.
- **Moving work does not remove it.** The storage reads what the engine would have read.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: where_work_happens
```

**5.1 Which files?** Write `files_to_open`: given the table metadata and some comparisons, the
files that might hold a row passing all of them. Decode the bounds yourself, from the bytes the
metadata stores. The graders check, for many predicates on every column, that you open every file
holding a match, and that you open no file whose bounds rule it out.

**5.2 Which directories?** Write `months_to_read`: given the paths of a table in Hive's layout and
a range of dates, the files whose month holds a day in the range, decided from the paths alone.
The graders try many ranges, including ones that end on the first of a month and ones that hold
no day at all.

**5.3 Diagnose the slow query.** No test. A colleague asks the table for one customer's orders,
`customer_id = 17`, and finds it no faster than reading the whole table. Your table scan, by its
metadata:

```{include} _generated/one-customer-table.md
```

Why did the table metadata rule out no file? What would the bounds have to look like for it to
rule some out, and what change to the way the table is written would make them look like that?
What would that change cost the chapter's query by date? A good answer reads the bounds in the
table, names a layout that serves the customer query, and says what it does to the query by
month.

## Where to go next

- **The table format's own account.** The [Apache Iceberg specification](https://iceberg.apache.org/spec/)
  describes manifests, the column bounds they keep, and the partitioning Iceberg derives from a
  column's values without putting them in a path.
- **Hive partitioning in DuckDB.** DuckDB's [Hive partitioning documentation](https://duckdb.org/docs/data/partitioning/hive_partitioning)
  says how it reads a column from a path and filters files by it.
- **Arrow's stream format.** The [Arrow columnar format](https://arrow.apache.org/docs/format/Columnar.html)
  specification describes the IPC stream the storage sends: a schema, then batches, in the same
  layout as in memory, so nothing is converted on arrival.
- **Where the idea comes from.** Michael Armbrust and others, *Delta Lake: High-Performance ACID
  Table Storage over Cloud Object Stores*, VLDB 2020, on why a table needs metadata beyond its
  files. Xiangyao Yu and others, *PushdownDB: Accelerating a DBMS Using S3 Computation*, ICDE
  2020, on filtering in the storage and what it saves.
- **A footer, byte by byte.** *[Parquet, byte by byte](https://github.com/snowch/parquet-book)*
  decodes the footer every file-by-file scan reads, in its chapter on how readers read.
