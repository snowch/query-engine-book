---
title: Joins
---

(joins)=
# Joins

## The question

Which side of a join does an engine hold, and what does holding it cost?

[ch07](#hash-aggregation) kept one entry per group in a hash table, and found that the table's
size against the cache decided what every lookup cost. A join pairs each row of one input with
the rows of the other whose key matches, and the usual way to do it holds one whole input in the
same kind of table. The engine chooses which input to hold. This chapter asks how it chooses, and
measures what the choice costs.

## Observe

The query gives each order its customer's country:

```{literalinclude} ../queries/orders_with_country.sql
:language: sql
```

DuckDB's plan:

```{include} _generated/orders-with-country-plan.md
```

1. **The join has two inputs, and they are not alike.** DuckDB draws the join's first child, the
   orders, and its second, the customers. It reads the second into a hash table first, and only
   then streams the first through it.
2. **DuckDB wrote down the second input's key range.** `Build Min` and `Build Max` are the
   smallest and largest customer id among the rows it holds. A key outside that range cannot
   match, so the range can be handed to the other input's scan as a filter. Here every order's
   customer is in range, and the filter rules nothing out.

The input a hash join reads into its table is its **build side**; the input it then streams past
the table, looking each row's key up, is its **probe side**. Together they make a **hash join**.
Only the build side is held, every row of it, until the join ends; the probe side passes through
a batch at a time. The same join written the other way round, with the customers first:

```{literalinclude} ../queries/customers_with_orders.sql
:language: sql
```

DuckDB plans it exactly as before: the customers are still the build side. Which input is held
is the planner's choice, not the query's order.

## Predict, then measure

Your engine's hash join builds ch07's table on the build side's keys, and holds the build rows
beside it, each at eight bytes a column plus eight for its link to the next row with the same
key. A probe reads the table's slots and then every build row it matches, through the cache
model.

Predict the cache misses of three joins: building on the customers and probing with the orders;
building on the orders and probing with the customers; and building on the enterprise customers
only, which a filter keeps before the build.

```lab
experiment: measure
of: joins
```

The panel draws what your engine and the cache model counted when the book was built. Its button
runs the same joins again in your browser.

- **Building on the small side keeps most of it in the cache.** The customers' rows and their
  table together are a little larger than the cache, so most probes find their lines there.
- **Building on the large side misses on nearly every row it matches.** The same rows come out.
  But the join now holds every order, many times the cache, and each customer's orders lie
  scattered through them.
- **A filter on the build side is the cheapest join of all.** It holds a quarter of the
  customers, which fit in the cache with room to spare. It joins fewer rows, since the orders of
  other customers find no match.
- **The cliff is the cache again.** The chart builds on more and more orders, keyed by their own
  ids, and probes with every order. The misses stay low while the build side fits in the cache,
  then climb towards one a probe.

## Building it

### Build, then probe

The join reads its whole build side before it asks the probe side for a row. Then, for each
probe row, one lookup, and a joined row for every build row it finds:

```{literalinclude} ../python/query_lab/join.py
:language: python
:start-at: def batches(self)
:end-before: @property
```

```run
experiment: measure
of: joins
```

Give each held row a cache line of its own, with `row * 64` in place of `row * self.row_bytes`
where the probe reads it, and run the panel's report on your edit: building on the customers now
misses about three times as often, because their rows no longer fit in the cache together.

The lookup is ch07's, with one difference: a probe never inserts. A key the build side lacks
stops at the first empty slot, and the row is dropped.

### The plans

Your engine has no planner yet, so it builds on whichever table the query names second. That is
the customers in the chapter's query, and the orders in the same query written the other way:

```{literalinclude} ../python/query_lab/plans.py
:language: python
:start-at: def orders_with_country(
:end-before: #: queries/top_orders.sql's and orders_by_amount.sql's order
```

The book's tests join from either side, with a filter on the build side, and with the orders
joined to themselves, and compare every row with DuckDB's.

## Compare

Your join beside DuckDB's:

```{include} _generated/orders-with-country-compare.md
```

And both ways of writing the query:

```{include} _generated/build-sides.md
```

- **Both engines join the same rows, and read every row of both inputs.** A join's
  rows in are its probe side's and its build side's together.
- **DuckDB built on the customers both times.** It chose the build side from its estimates of
  the two inputs' sizes, and the text of the query did not matter.
- **Your engine built on whichever side came second.** Written with the orders second, it held
  every order, several times the bytes, and missed the cache many times as often, for the same
  result.

Which side a join holds decides what it costs. DuckDB probes, with a million rows, build sides of
more and more rows, here in your browser:

```timed
of: build_sides
```

- **The same probe costs more against a bigger build side.** Every case looks up a million keys
  and finds each one. A small build side's table stays in the cache, and each lookup is a hit; a
  large one's does not, and a lookup waits for memory.
- **That is why an engine builds on the smaller side.** Built on the larger side, the same join
  holds more, and every probe pays for it.

## What this cannot tell you

- **What the misses cost on another machine.** As in ch07, the counts compare the ways, and the
  timing shows what a bigger build side costs on yours.
- **How DuckDB lays out what it holds.** DuckDB keeps build rows in its own row format, with
  strings stored apart, and chains a key's rows through pointers. The model gives every value
  eight bytes and one read.
- **What happens when the build side does not fit in memory.** DuckDB partitions the build side
  by its keys' hashes and can write partitions to disk, joining one partition at a time. Your
  engine holds everything.
- **Whether the range filter helped.** DuckDB did not report what its range filter skipped, and
  on this data it could skip nothing.

## What this means for your design

- **Let the build side be small, and make it smaller.** Filter the table you join to before the
  join, not after: a filter on the build side shrinks what is held.
- **Select only the columns you need from the build side.** Every column of every held row is
  held until the join ends.
- **Check which side your engine holds.** A planner chooses from its estimates, and a bad
  estimate builds on the wrong side. `EXPLAIN` shows the choice, as the join's second child.
- **Beware keys that repeat on both sides.** A join makes a row for every pair of matching rows,
  and a key that appears many times on both sides makes the product of those counts. Problem 8.3
  measures one.

## Key takeaways

:::{div}
:class: takeaways

- **A hash join holds its build side and streams its probe side.** Memory and cache misses follow
  the build side's size.
- **The planner chooses the build side, not the query's text.** DuckDB built on the customers
  however the query was written; your engine, with no planner, did as the text said.
- **The same cliff as ch07.** While the held rows fit in the cache, probes are cheap; past it,
  nearly every match is a miss.
- **A join's output can dwarf its inputs.** Every matching pair is a row.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: joins
```

**8.1 Merge the two sides.** Write `merge_join`: a join of two inputs already sorted by their key,
that walks both from the front, as a **merge join** does, with no table at all. The graders join
many random inputs, and the orders with their customers, and compare your rows with DuckDB's, in
order.

**8.2 A filter from the build side.** Write `bloom` and `might_contain`: a Bloom filter, which
[ch04](#statistics-and-pruning) met stored in a file, here built from the build side's keys, a
set of bits the probe side's scan can test to drop rows that cannot match before the join sees
them. It may let a key through that is not there, but never
stops one that is. The graders build it from the enterprise customers, check that no enterprise
customer is ever stopped, and check that other keys get through about as often as the filter's
arithmetic says they should.

**8.3 Diagnose the slow query.** No test. A colleague pairs each order with the same customer's
other orders, joining the orders to themselves on the customer, and the query never seems to
finish:

```{include} _generated/self-join.md
```

Why does the join make so many rows from so few? Why does one customer account for most of them?
What would you ask the colleague to compute instead, if what they want is, for each order, how
many other orders its customer placed? A good answer explains the product of the counts, points
at the skew in the customers, and proposes a query that aggregates before it joins.

## Where to go next

- **Hash joins, tuned to the machine.** Spyros Blanas, Yinan Li and Jignesh Patel, *Design and
  Evaluation of Main Memory Hash Join Algorithms for Multi-core CPUs*, SIGMOD 2011; and Cagri
  Balkesen, Jens Teubner, Gustavo Alonso and M. Tamer Özsu, *Main-Memory Hash Joins on Multi-Core
  CPUs: Tuning to the Underlying Hardware*, ICDE 2013, on partitioning the build side to fit the
  cache.
- **The filter.** Burton Bloom, *Space/Time Trade-offs in Hash Coding with Allowable Errors*,
  Communications of the ACM, 1970: the filter of problem 8.2, and its arithmetic.
- **DuckDB's join.** DuckDB's [source](https://github.com/duckdb/duckdb), in
  `src/execution/join_hashtable.cpp`, holds its hash join's table and the build side's rows.
