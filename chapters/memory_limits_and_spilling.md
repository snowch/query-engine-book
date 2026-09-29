---
title: Memory limits and spilling
---

(memory-limits-and-spilling)=
# Memory limits and spilling

## The question

What does an engine do when an operator needs more memory than it is allowed?

The aggregate of [ch07](#hash-aggregation), the join of [ch08](#joins) and the sort of
[ch09](#sorting-and-top-k) each hold rows until their input ends: every group, the whole build
side, every row to sort. Each assumed the memory was there. An engine runs under a limit, set
by the machine or by the person running it, and many queries at once share it. This chapter
takes the sort of ch09, gives it less memory than its rows need, and counts what finishing
anyway costs.

## Observe

The query is ch09's full sort:

```{literalinclude} ../queries/orders_by_amount.sql
:language: sql
```

DuckDB takes a **memory limit** as a setting, and a temporary directory where it may write what
does not fit. Run within a few small limits, with a temporary directory and without, beside
ch09's top ten:

```{include} _generated/memory-limits.md
```

1. **Below some limit, nothing finishes.** DuckDB needs a few blocks of memory for any query:
   to read the file, and to hold what it is working on.
2. **A little above it, the sort finishes only if it can write to disk.** With a temporary
   directory, DuckDB writes what does not fit and reads it back later. Without one, the same
   sort runs out of memory.
3. **The top ten finishes where the sort cannot.** It holds ten rows, not twenty thousand, and
   never needs to write anything.

Writing what does not fit to temporary storage, to read it back later, is **spilling**. It lets
a query finish in less memory, and it costs bytes written and read that an in-memory run never
pays.

## Predict, then measure

Your engine's sort can now run within a limit. It holds batches until the next would take it over
the limit, sorts what it holds into a sorted run, as ch09 called the pieces a sort finds in order,
and spills the run as Arrow IPC. When the input ends, it merges the runs: a merge reads the first
batch of each run it merges, and hands up the smallest row, again and again. The number of runs
one merge reads at once is its **fan-in**. With more runs than the fan-in, a pass merges them a
fan-in at a time into fewer, longer runs, spilled again, until one pass can merge them all. The
whole is an **external sort**.

Predict the bytes each sort spills: with memory for every row; with memory for half the rows;
and with memory for a tenth of them, merging two runs at a time.

```lab
experiment: measure
of: spilling
```

The panel draws what your engine counted when the book was built. Its button runs the same sorts
again in your browser.

- **Memory for every row spills nothing.** It is ch09's sort.
- **Memory for half spills every row once.** Two runs, each written once and read back once, and
  one merge, which hands the rows up as it goes.
- **A tenth, two at a time, spills every row several times.** Ten runs take several passes of
  merging two at a time, and every pass but the last writes every row again.
- **Memory saves less than the fan-in does.** The chart sorts within more limits, with a fan-in
  of two and of eight. Less memory makes more runs, but a larger fan-in merges them in fewer
  passes, and each pass it saves is a write and a read of every row.

## Building it

### Runs, then merges

The sort fills its memory, sorts, and spills; then merges, a pass at a time, until one pass is
enough:

```{literalinclude} ../python/query_lab/spill.py
:language: python
:start-at: def batches(self)
:end-before: def _sorted(
```

```run
experiment: measure
of: spilling
```

Hold rows up to twice the limit before spilling, `2 * self.memory_limit` in the test that cuts a
run, and run the panel's report on your edit: the sort within half the rows' bytes spills nothing
at all, and the one within a tenth makes half as many runs and one pass fewer. It does so by
holding twice the memory it was allowed.

### A run, written and read

A run is written in batches, so a merge can read it back one batch at a time and hold one batch
of each run it merges:

```{literalinclude} ../python/query_lab/spill.py
:language: python
:start-at: def _spill(
:end-before: def schema(self)
```

The book's tests sort within many limits and fan-ins and require DuckDB's order every time. They
check that every byte written is read back, that each pass but the last writes every row, and
that a larger fan-in never spills more.

## Compare

DuckDB reports neither what it spilled nor the memory it used, in the pinned version, so the
comparison is the result: your external sort hands up DuckDB's rows, in DuckDB's order, within
every limit the tests try, and DuckDB's own sort finishes within a limit only when it may spill.

## What this cannot tell you

- **What the disk costs.** The counts are bytes written and read. On a laptop's disk or in object
  storage, writing a byte costs far more than holding it, which is the whole case against
  spilling.
- **How much memory DuckDB used.** It reports the limit it was given and whether it ran out, not
  its peak. The limits in the table are where the pinned version succeeds on this data.
- **What DuckDB spills.** DuckDB can spill its hash aggregates and joins too, by partitioning
  their rows by hash and holding one partition at a time. Your engine spills only its sort.
- **Your engine's memory beyond its rows.** The limit counts the Arrow buffers the sort holds.
  The Python values it sorts them as are larger, and not counted.

## What this means for your design

- **Set a memory limit, and a place to spill.** Without a temporary directory, an operator that
  outgrows memory fails the query; with one, it slows down instead.
- **Prefer the query that needs less memory.** A `LIMIT`, a filter before the join, a narrower
  `GROUP BY`: each shrinks what an operator holds, and so what it spills.
- **Give a spilling sort enough memory to merge in one pass.** The bytes spilled depend on the
  passes, and one pass needs only a batch of memory per run.
- **Watch the spill, not the time.** An engine that reports the bytes it spilled, as Spark and
  Trino do, tells you why a query slowed down; the time alone does not.

## Key takeaways

:::{div}
:class: takeaways

- **An operator that holds rows needs memory for them, or somewhere to put them.** Sorts,
  aggregates and joins all hold rows.
- **Spilling trades memory for bytes written and read.** A sort that spills writes every row at
  least once.
- **The merge's fan-in decides how many times.** Each pass but the last writes every row again.
- **A top-k needs no disk.** It holds k rows whatever the input.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: memory_limits_and_spilling
```

**10.1 Cut the runs.** Write `runs_for`: given the sizes of the batches a sort reads and its memory
limit, how many batches each sorted run holds. The graders run the book's external sort on
batches of those sizes and compare its runs with yours.

**10.2 Plan the merges.** Write `merge_plan`: given the runs and the fan-in, the merge passes the
sort makes and the runs those passes write. The graders run the book's sort on as many runs, for
several fan-ins.

**10.3 Diagnose the slow sort.** No test. A colleague's sort runs within a tenth of the memory its
rows need. They try several fan-ins:

```{include} _generated/fan-in.md
```

Why does a fan-in of two spill every row four times, and a fan-in of sixteen only once? Why does
a fan-in of eight spill every row twice, though ten runs are barely more than eight? What first
pass would get ten runs down to eight while writing far fewer rows? A good answer counts the
passes, explains why each writes every row, and proposes a first pass that merges only as many
runs as it must.

## Where to go next

- **External sorting.** Donald Knuth, *The Art of Computer Programming*, volume 3, section 5.4:
  runs, merges, and how many passes a merge of a given fan-in needs.
- **Spilling in DuckDB.** Laurens Kuiper,
  [Fastest Table Sort in the West](https://duckdb.org/2021/08/27/external-sorting.html), on how
  DuckDB's sort spills and merges; and DuckDB's documentation on the
  [memory_limit and temp_directory settings](https://duckdb.org/docs/configuration/overview).
- **Hash joins that spill.** Goetz Graefe, *Query Evaluation Techniques for Large Databases*, ACM
  Computing Surveys, 1993: partitioning a join's inputs so each partition fits in memory, the way
  engines spill joins and aggregates.
