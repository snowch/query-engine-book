---
title: Hash aggregation
---

(hash-aggregation)=
# Hash aggregation

## The question

How does an engine find a row's group, and what does the number of groups cost?

The operators so far forget each row as soon as they are done with it. A filter tests a row and
passes it on or drops it; a projection computes from it and moves on. A `GROUP BY` cannot forget:
every row belongs to a group, and the group must be kept somewhere until the last row has arrived,
since any row might belong to any group. So for every row the engine must find the row's group
among all the groups it has seen, and [ch02](#batches-in-memory) showed that what a read costs
depends on where in memory it lands. This chapter asks where a group lives, and what finding it
costs as the groups multiply.

## Observe

The query counts each customer's orders, and what they spent:

```{literalinclude} ../queries/orders_per_customer.sql
:language: sql
```

DuckDB's plan:

```{include} _generated/orders-per-customer-plan.md
```

And the same aggregates grouped by the order's status instead:

```{literalinclude} ../queries/orders_per_status.sql
:language: sql
```

```{include} _generated/orders-per-status-plan.md
```

1. **DuckDB chose a different operator for each key.** Grouped by the status, a string, it builds
   a hash table. Grouped by the customer id, it uses a `PERFECT_HASH_GROUP_BY`.
2. **It read the key's range before it read a row.** The projection under the perfect aggregate
   squeezes the customer id into two bytes, subtracting the smallest id, which it took from the
   file's statistics. The ids run over a range small enough to give every possible customer a
   slot of its own, found by subtracting, with nothing to search.
3. **Its estimate of the groups is a guess.** For the status, which holds a handful of values, it
   expects the groups to number half the rows it reads. A planner that does not know how many
   distinct values a column holds has to guess, and this is DuckDB's guess.

A **hash table** is the general way to find a group. It is an array of slots. A key's hash, a
number computed from the key, picks the slot to look in first; if another key's group is there,
the table looks in the next slot, and the next, until it finds the key or an empty slot. Keeping
the groups in the array itself this way, rather than in lists hanging off it, is **open
addressing**, and trying the next slot each time is **linear probing**. When a key's range is
small and known, an engine can skip the hashing altogether: a slot for every possible key, found
by subtracting the smallest. DuckDB calls that a **perfect hash aggregate**.

## Predict, then measure

Your engine's hash table works as DuckDB's does. Each slot takes sixteen bytes, eight for the key's
hash and eight for its group's number, and the table doubles when three quarters of its slots are
full, moving every group to a new, larger array. Every slot a lookup looks at is a read of the
cache model from [ch02](#batches-in-memory).

Predict the cache misses of grouping the orders, in date order, by three keys: the status, which
holds a handful of values; the customer id, which holds about a thousand; and the order id, which
holds a different value on every row. The panel shows the number of rows for each, and says how
large the cache is.

```lab
experiment: measure
of: aggregation
```

The panel draws what your engine and the cache model counted when the book was built. Its button
runs the same lookups again in your browser.

- **A handful of groups costs a handful of misses.** The status table is a few lines, fetched once
  and never pushed out.
- **A thousand groups cost about a miss a group.** The customer table ends the size of the cache,
  so each group's line is fetched about once, and then found there.
- **A group for every row costs more misses than there are rows.** The order table outgrows the
  cache many times over, and each doubling moves every group to lines the cache has never held.
- **The cliff is the cache.** The chart folds the order ids onto more and more groups. The hash
  table's misses follow the groups while the table fits in the cache, then jump to about one a
  row. The perfect table misses far less, because the ids arrive in order: it walks its slots
  from first to last, and fetches each line once, until even it outgrows the cache.

## Building it

### Finding a group

A lookup hashes the key, starts at the slot its hash's low bits name, and probes until it finds
the key or an empty slot. An empty slot means a new group: the key takes the slot, and the table
doubles if it is now more than three quarters full:

```{literalinclude} ../python/query_lab/aggregate.py
:language: python
:start-at: def find(self, key: object)
:end-before: def get(self, key
```

```run
experiment: measure
of: aggregation
```

Make the table double when half full instead, with `self.capacity // 2` in place of
`self.capacity * LOAD`, and run the panel's report on your edit: the probes fall, and for the
order ids the table doubles once more, to twice the bytes.

The hash itself is the book's own function, not Python's: Python's hash of a string changes from
one run to the next, and the counts must be the same everywhere.

### The perfect table

With a key's range known, the slot is the key less the smallest key. One probe, every time:

```{literalinclude} ../python/query_lab/aggregate.py
:language: python
:start-at: def find(self, key: int)
:end-before: @property
```

### The aggregate

The operator looks every row up, and moves its group's running state on: a count, a sum, a
minimum, a maximum. Nothing can be handed up until the child has handed up its last row, so the
operator holds every group until then, and hands them all up in one batch:

```{literalinclude} ../python/query_lab/aggregate.py
:language: python
:start-at: def batches(self)
:end-before: def _result(
```

### The plan

A scan and the aggregate. Told to be perfect, the plan reads the range of the customer ids from
the file's statistics, as DuckDB did, before it reads a row:

```{literalinclude} ../python/query_lab/plans.py
:language: python
:start-at: def orders_per_customer(
:end-before: def orders_per_status(
```

The book's tests group the orders by several keys, one column and two, and compare every group's
count, sum, minimum, maximum and average with DuckDB's. They check that the table never fills
more than three quarters of its slots, and that a perfect table finds the same groups with one
probe a row.

## Compare

Your plan beside DuckDB's:

```{include} _generated/orders-per-customer-compare.md
```

And your engine's two tables, on the same customer ids:

```{include} _generated/hash-and-perfect.md
```

- **Both engines find the same groups.** SQL promises no order for them, so the tests compare
  them sorted: each engine hands its groups up in the order its table holds them.
- **The perfect table does less of everything.** One probe a row where the hash table needed more,
  no resizes, a smaller array, and a fraction of the misses: its array fits in the cache, and it
  never moves.
- **DuckDB made the same choice from the same statistics.** It chose the perfect aggregate
  because the file's statistics gave the ids' range, and the range was small.

The cliff the model counted is one you can time. DuckDB groups a million rows by a hashed key
into more and more groups, here in your browser:

```timed
of: groups
```

- **The same rows cost more as the table grows.** Every case reads the same million rows and
  adds up the same values. What changes is the table: a few thousand groups fit in the cache,
  and a million do not, so most lookups wait for memory.
- **Past the cache, every lookup costs more.** The same rows take many times as long, because
  each lookup is a miss rather than a hit, and a miss costs many times as much. That is the cost
  the model's misses stand for.

## What this cannot tell you

- **What a miss costs on another machine.** The cache model counts misses. A real one costs on
  the order of a hundred cycles, a hit a few; the timing above shows what they add up to on yours.
- **What a real table holds.** DuckDB's slots point into a separate area that holds each group's
  key and aggregates, so a lookup reads a second place; a string's bytes live in a third. The
  model reads one slot and nothing else.
- **What moving the groups costs.** Each doubling writes every group into the new array. The
  cache model counts reads, not writes.
- **How DuckDB handles a table larger than the cache.** It partitions the rows by their hashes
  and builds a table per partition, and can spill partitions to disk. Your engine builds one table
  and keeps it in memory, however large it grows.

## What this means for your design

- **Group by what the question needs, and no more.** Every column added to a `GROUP BY`
  multiplies the groups, and the table grows with them. Problem 7.3 measures it.
- **Keep keys compact.** A whole-number id from a dense, small range lets an engine use a perfect
  table, and statistics tell it the range. A sparse or random id, or a string, needs a hash table.
- **Aggregate early, and combine.** Aggregates like counts and sums can be computed on parts of
  the data and combined, which is how an engine aggregates many files or many threads at once.
  Problem 7.2 combines them.
- **Sorted input needs no table.** When the rows arrive sorted by the key, each group ends where
  the key changes, and an engine can aggregate one group at a time. It is worth sorting on the
  keys you group by most.

## Key takeaways

:::{div}
:class: takeaways

- **An aggregate remembers every group until the last row.** Finding a row's group is a lookup
  in a table the size of the groups.
- **A hash table probes slots, and the cache decides what a probe costs.** While the table fits
  in the cache, it misses about once a line; past that, about once a row.
- **A small, known range needs no hash.** A perfect table finds a group by subtracting, and
  DuckDB takes the range from the file's statistics.
- **A planner guesses the groups when it cannot count them.** DuckDB guessed half its input.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: hash_aggregation
```

**7.1 How many probes?** Write `probes`: the slots linear probing looks at to insert keys with
given hashes into an empty table that never grows. The graders compare your count with the book's
table on many random tables, and on runs of keys that all hash to the same slot.

**7.2 Combine the parts.** Write `combine`: given **partial aggregates**, each group's count, sum,
minimum and maximum over one part of the rows, the final aggregates over all of them, with the
average. The graders cut the orders into parts, aggregate each part with DuckDB, and compare what
you combine with DuckDB's aggregates over the whole file.

**7.3 Diagnose the slow query.** No test. A colleague's report groups the orders by customer, and
was quick. They add a second column to the `GROUP BY`, and it slows down far more than the extra
column's bytes explain:

```{include} _generated/wider-keys.md
```

Why did the second key multiply the cache misses, when the rows and the columns read barely
changed? Why does the date multiply them so much more than the status? What would you suggest
instead, if the report needs each customer's orders per day? A good answer relates the groups to
the table's bytes and the cache's size, and proposes a way to keep the table small, or to need no
table at all.

## Where to go next

- **Hash tables, measured.** Stefan Richter, Victor Alvarez and Jens Dittrich, *A Seven-Dimensional
  Analysis of Hashing Methods and its Implications on Query Processing*, VLDB 2015: open
  addressing and its rivals, by load factor, key distribution and workload.
- **DuckDB's aggregate.** Hannes Mühleisen and Mark Raasveldt,
  [Parallel Grouped Aggregation in DuckDB](https://duckdb.org/2022/03/07/aggregate-hashtable.html),
  on its table's layout, its partitioning, and how threads combine their tables.
- **Linear probing's arithmetic.** Donald Knuth, *The Art of Computer Programming*, volume 3,
  section 6.4, on how long a probe sequence runs as the table fills.
