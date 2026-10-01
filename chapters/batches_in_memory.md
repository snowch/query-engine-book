---
title: Batches in memory
---

(batches-in-memory)=
# Batches in memory

## The question

What does a batch of rows look like in memory, and why does the order you touch it in matter?

[ch01](#the-plan-is-the-map) counted rows and batches as they moved between operators, and the
most memory each operator held: the bytes in the Arrow buffers of its largest batch. It never
said what those bytes are, or whether the order an operator reads them in changes what it costs.
A filter reads its rows in the order they arrived. A sort, a join or a lookup reads them in an
order of its own. Both read the same rows, so every counter in [ch01](#the-plan-is-the-map)
comes out the same. Yet one of them is far more work for the machine. To see why, you need the
bytes of a batch, and a way to count what reading them costs.

## Observe

The query asks for every order, in date order. It reads `orders-shuffled`: the same orders as
the file [ch01](#the-plan-is-the-map) read, written by the same generator in a random order
([The fixtures](#the-fixtures)). `file_row_number` is a column DuckDB adds when you ask for it:
the position each row had in the file.

```{literalinclude} ../queries/orders_by_date.sql
:language: sql
```

DuckDB's plan, from `EXPLAIN`:

```{include} _generated/orders-by-date-plan.md
```

Read it from the bottom, as the rows travel.

1. **The scan reads every column the query names.** A sort needs the whole row: whatever it puts
   first, it has to hand up with all of its columns.
2. **A projection narrows two columns before the sort.** In the pinned DuckDB,
   `__internal_compress_integral_usmallint`
   stores `file_row_number` and `order_id` in two bytes a row instead of eight. DuckDB can,
   because its statistics for the two columns say how far apart their smallest and largest
   values are, and the difference fits in two bytes. The projection at the top widens them again. DuckDB shrinks what it is about
   to move, because the sort moves every row.
3. **The sort carries no estimate.** Whatever it takes in, it hands out; only the order changes.

The first rows of the result say where each one came from:

```{include} _generated/orders-by-date-rows.md
```

The first orders of the year sat all over the file. To hand them up in date order, the engine
reads each row from wherever it sat. Reading rows by position, in an order you choose, is a
**gather**: row `k` of the output is row `positions[k]` of the input, for each column in turn.
In the sorted file the positions would count up from zero, and the gather would read the rows
where they lie, one after the next.

DuckDB can hand its result over as Arrow arrays, which is how the book reads it. Each column
arrives as a few contiguous buffers of bytes:

```{include} _generated/orders-by-date-buffers.md
```

Three things stand out.

1. **A fixed-width column is one buffer of values.** `order_id` is eight bytes a row,
   `order_date` four. Row `i`'s value starts at byte `i` times the width, so finding a row is
   arithmetic.
2. **A string column is two buffers.** The data buffer holds every string's bytes end to end. The
   **offsets** buffer holds, for each row, where its string starts in the data, plus one more
   offset where the last one ends: four bytes a row, and four more.
3. **Every column carries a validity bitmap.** A **validity bitmap** holds one bit per row, set
   where the row has a value and clear where it is null, so it takes one byte for every eight
   rows. `note` is the only column with nulls, and DuckDB hands over a bitmap for the others too.

Those buffers are the rows. What a gather costs depends on the order it reads them in, and
counting that needs a model of the memory underneath.

## Predict, then measure

A processor does not read memory a byte at a time. Memory reaches it in **cache lines**,
blocks of consecutive bytes, and it keeps the lines it used recently in a small, fast cache. A
read whose line is in the cache is a **cache hit**. Any other read is a **cache miss**: the
whole line is fetched from memory first, and the line used longest ago is pushed out to make
room. The book's cache model has these settings:

```{literalinclude} ../python/query_lab/cache.py
:language: python
:start-at: #: A line of
:end-before: @dataclass
```

The experiment gathers one column, `amount`, into date order through the model, twice: once
from `orders-sorted`, where date order is the order the rows are stored in, and once from
`orders-shuffled`. Both gathers read the same rows and produce the same column. Predict how many
lines the cache fetches in each.

You have what you need. The panel gives the column's size in lines and the cache's size, and
draws, for each file, the line of the column that reads spaced evenly through the gather fall
in. Two things
decide the answer. A line holds several rows' values, so a read of the next row usually finds
its line already fetched. And a line stays in the cache only until enough other lines push it
out: the cache holds a fraction of the column.

```lab
experiment: gather
column: amount
```

The panel draws what the book's engine counted when the book was built. Its button runs the same
report again in your browser, under Pyodide, and says whether your browser counted the same.

Compare the two gathers.

- **In storage order, each line is fetched once.** The lines fetched equal the column's lines.
  Every byte fetched was used, and each line served every row it held before the next was
  needed.
- **In random order, most reads are misses.** A read hits only when its line is among the few
  the cache still holds, and the cache holds a small share of the column. Each miss fetches a
  whole line to use one value of it, and the same line is fetched again and again.
- **Nothing [ch01](#the-plan-is-the-map) counted tells the two apart.** Rows in and rows out are
  the same. What differs is the bytes the processor had to fetch, which is why this chapter
  needs a model to see it.

The model says the shuffled gather fetches many more lines. Your processor can say what that
costs. The panel below gathers a column far larger than any cache, with pyarrow's own `take`, once
in storage order and once shuffled, and times both in your browser:

```timed
of: gathers
```

- **The shuffled gather is slower, for the same values moved.** Both read every value once and
  write the same column; only the order of the reads differs. The difference is the misses the
  model counted, paid on your processor.
- **The gap in time is smaller than the gap in lines.** A real processor has several levels of
  cache and fetches ahead of a read in storage order, and a gather does more than wait for lines.
  The model counts what the order changes; the time says how much of the work that is, here.

## Building it

Your engine's scan built its arrays with pyarrow in [ch01](#the-plan-is-the-map). It now builds
them itself, buffer by buffer, so every byte ch01 counted as memory is one this chapter wrote.

### Arrays from raw buffers

A validity bitmap sets bit `i % 8` of byte `i // 8` for each row `i` that holds a value, counting
from the least significant bit. Arrow lets an array with no nulls leave its bitmap out, and your
engine does:

```{literalinclude} ../python/query_lab/memory.py
:language: python
:start-at: def validity_bitmap(
:end-before: def is_valid(
```

```run
tests: test_memory.py
select: bitmap or built_by_hand or no_nulls or offset
```

Try counting from the other end of each byte, `1 << (7 - i % 8)`, and run the tests on your edit:
the array still builds, and pyarrow reads the wrong rows as null.

A fixed-width array packs each value at its row's place in one buffer, and a string array writes
the offsets as it appends each string's bytes. `pa.Array.from_buffers` wraps the buffers as an
array without copying them:

```{literalinclude} ../python/query_lab/memory.py
:language: python
:start-at: def fixed_width_array(
:end-before: def array_from(
```

### Reading a bit

Reading the bitmap back is the same arithmetic in reverse. One detail matters: a slice of an
array shares its parent's buffers and starts some rows into them, so the bit to read is the
slice's offset plus the row:

```{literalinclude} ../python/query_lab/memory.py
:language: python
:start-at: def is_valid(
:end-before: def fixed_width_array(
```

### The cache and the gather

The model's read touches every line its bytes fall in, and counts each as a hit or a miss:

```{literalinclude} ../python/query_lab/cache.py
:language: python
:start-at: def read(self, buffer
:end-before: @property
```

```run
experiment: gather
column: amount
```

Edit the cache so it never pushes a line out, and run the gather again: the shuffled gather's
misses fall to the column's size in lines, because the cache has become the whole of memory.

The gather reads each row the positions ask for, through the cache, in the order they ask for
them: the bit, then the value; for a string, its two offsets, then its bytes. It builds the
result with the functions above:

```{literalinclude} ../python/query_lab/memory.py
:language: python
:start-at: def gather(
```

### The query, by hand

Your engine has no sort yet: finding the order is a sort, and sorting is Part III. Here pyarrow
finds it, and your engine does the part the experiment measured, moving each column into that
order:

```{literalinclude} ../python/query_lab/plans.py
:language: python
:start-at: def in_date_order(
:end-before: #: Every column of the orders files
```

The book's tests check that each array your engine builds is the array pyarrow builds from the
same values, buffer for buffer; that a gather gives the rows a take gives; that the model counts
each line once when a column is read in order; and that the order your engine finds is the one
DuckDB's `file_row_number` shows.

## Compare

Your engine returns DuckDB's result, row for row, column for column. Here are its buffers beside
DuckDB's:

```{include} _generated/orders-by-date-compare.md
```

- **Values, offsets and data are the same size in both.** Arrow's layout fixes them: the width
  of a type times the rows, and four bytes an offset. Two engines that share the format agree on
  the size of every buffer.
- **DuckDB keeps a bitmap for every column; your engine only where there are nulls.** Arrow allows
  both. DuckDB's bitmaps cost one byte per eight rows for columns that never need them. Your
  engine saves those bytes, and every reader of its arrays has to check whether the bitmap is
  there before reading a bit.
- **DuckDB reports nothing about what its sort fetched from memory.** Its profile counts rows,
  not lines. The cache model is the book's way to count them, and DuckDB's narrowing of two
  columns before its sort is its own answer to the same cost.

## What this cannot tell you

- **How long a gather takes on another machine.** The model counts lines, not time. The timing
  above shows what a shuffled gather costs on yours; how much a miss costs against a hit depends
  on the machine, which is why the page keeps no time.
- **A real processor's caches.** The model has one level where a processor has several, lets any
  line sit anywhere where real caches restrict each line to a few places, and fetches nothing
  ahead of time. A real processor notices a read in storage order and fetches the next lines
  before they are asked for, so the sorted gather is cheaper still. The model counts only the
  gather's reads of its input: not the positions it reads them from, not the result it writes.
- **How DuckDB sorts.** DuckDB sorts in a layout of its own and hands over Arrow at the end. The
  model counts your engine's gather, not DuckDB's work.
- **How to find the order.** The sort that produced the positions is Part III's.
- **What the file costs to read.** In memory, Arrow's buffers are uncompressed. On disk, Parquet
  compresses them, and [ch03](#projection-and-filter-pushdown) counts the bytes a scan fetches.

## What this means for your design

- **Store data in the order you read it.** A file sorted on the column your queries order by,
  join on or look up by turns every later gather into a read in storage order. The panel's two
  gathers read the same rows, and the shuffled one fetched many times the lines.
- **Narrow values move cheaper.** A line holds twice as many four-byte values as eight-byte ones,
  so a gather in storage order fetches half the lines. DuckDB narrows columns before it sorts for
  that reason. Choose the narrowest type that holds your values.
- **Ask only for the columns you need before a sort or a join.** Each column is gathered
  separately, and each pays its own lines. A wide string column pays for its offsets and its
  bytes.
- **Order only matters once the data outgrows the cache.** A column that fits in the cache is
  fetched once, whatever order you read it in. The cost of a random order grows with the share
  of the column the cache cannot hold.

## Key takeaways

:::{div}
:class: takeaways

- **A batch is buffers.** Each column is a validity bitmap and a values buffer, or, for strings,
  a bitmap, offsets and data, so finding a row is arithmetic on positions.
- **Memory moves in lines.** Reading one value brings in its whole line, and the cache keeps a
  few recent lines.
- **Order decides how many lines a gather fetches.** In storage order each line is fetched once;
  in random order nearly every read fetches a line of its own.
- **Row counts cannot see it.** The same rows in the same number came out of both gathers; only
  the bytes fetched differ.
- **Two engines that share Arrow agree on the buffers.** Your engine and DuckDB built buffers of
  the same sizes, and differ only in whether a column with no nulls keeps its bitmap.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: batches_in_memory
```

**2.1 Compact a slice.** Write `compact`: a copy of an `int64` array whose buffers start at its
first row. A slice shares its parent's buffers, so its first row can sit in the middle of a byte
of the bitmap. Your copy moves every bit to its new place, keeps no bitmap when there are no
nulls, and leaves every bit past the last row clear. The graders slice arrays at every offset
within a byte and beyond, and refuse pyarrow's and the book's builders: you move the bits
yourself.

**2.2 Read in order.** Write `gather_in_order`: the result of a gather, reading the input in the
order its rows are stored, whatever order the positions ask for, and putting each value where
the result needs it. The graders give it the date order of the shuffled file, a backwards order
and an order with repeats. They check the result, check that no read goes back to an earlier
row, and check that the cache fetched each line once. Engines use the same idea when they look
rows up in a large table: they sort or partition the positions first, and pay for that to save
the lines.

**2.3 Diagnose the slow query.** No test. A colleague's report runs the chapter's query to show
the orders of each day, and uses only `order_id` and `amount`. Your engine gathered every column
of it into date order, from each file:

```{include} _generated/orders-by-date-gathers.md
```

Which columns cost the most to gather from the shuffled file, measured against their size, and
why do the string columns cost more than their bytes suggest? What would you change in the
query, and what in the way the orders are stored? A good answer names the column that costs
most, explains the extra lines a string's offsets and bytes each fetch, predicts the lines the
rewritten query would fetch from each file, and says what the sorted file's gathers cost against
the column sizes and why.

## Where to go next

- **Arrow's layout.** The [Arrow columnar format specification](https://arrow.apache.org/docs/format/Columnar.html)
  defines the buffers of every type, the validity bitmap's bit order, and the padding and
  alignment of buffers.
- **Memory and caches.** Ulrich Drepper, *What Every Programmer Should Know About Memory*, 2007.
  Cache lines, associativity and prefetching, and what each costs, from the hardware up.
- **Batches and the cache.** Peter Boncz, Marcin Zukowski and Niels Nes, *MonetDB/X100:
  Hyper-Pipelining Query Execution*, CIDR 2005. Why engines work on batches of a column at a
  time, sized to stay in the cache.
- **DuckDB's narrowing.** The compressed materialization optimizer in DuckDB's source
  (`src/optimizer/compressed_materialization.cpp`) is the projection this chapter's plan showed.
- **Another engine, built the same way.** Andy Grove's *How Query Engines Work* builds its engine
  on Arrow arrays too, in its own order.
