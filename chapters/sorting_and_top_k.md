---
title: Sorting and top-k
---

(sorting-and-top-k)=
# Sorting and top-k

## The question

What does putting rows in order cost, and how much of it does a `LIMIT` save?

Like a `GROUP BY` in [ch07](#hash-aggregation), an `ORDER BY` cannot hand up anything until it
has seen everything: the last row read might be the first in order. It holds every row, and
compares them until they are in order. Yet most queries that sort want only the first few rows:
the ten largest orders, the latest hundred events. This chapter counts what a sort compares, and
what an engine saves when the query says how few rows it wants.

## Observe

The query asks for the ten largest orders:

```{literalinclude} ../queries/top_orders.sql
:language: sql
```

DuckDB's plan:

```{include} _generated/top-orders-plan.md
```

And the same query with no `LIMIT`:

```{literalinclude} ../queries/orders_by_amount.sql
:language: sql
```

```{include} _generated/orders-by-amount-plan.md
```

1. **With a `LIMIT`, there is no sort.** DuckDB replaced the `ORDER BY` and the `LIMIT` with one
   operator, `TOP_N`, that keeps ten rows. Without the `LIMIT`, it plans an `ORDER_BY` that
   sorts every row.
2. **Before a full sort, DuckDB narrows the rows.** The projection under the `ORDER_BY` squeezes
   the order and customer ids into two bytes each, using the file's statistics, as it did for the
   aggregate in [ch07](#hash-aggregation). Every byte of a row is moved many times in a sort.
3. **DuckDB does not guess how many rows the `TOP_N` hands up.** It knows: ten, or fewer.

The first k rows of an order, found without sorting every row, are a **top-k**. The trick is to
keep only k rows, and to know which of them is the worst: each new row need only be compared with
that one, and most rows lose at once.

## Predict, then measure

Your engine sorts with Python's own sort, which is a merge sort that first looks for **sorted
runs**, stretches of the input already in order, and merges them. Its top-k keeps the best rows
so far in a **heap**, an array arranged so that the worst row kept is always first.

Predict the comparisons each makes, for twenty thousand rows: sorting the shuffled orders by
amount; sorting the orders by date, in the file that stores them by date; and finding the ten
largest by amount.

```lab
experiment: measure
of: sorting
```

The panel draws what your engine counted when the book was built. Its button runs the same sorts
again in your browser.

- **A sort of shuffled rows compares each row many times.** For rows in no order, a sort makes
  on the order of the rows times the base-two logarithm of the rows, a little under that for this
  sort.
- **A sort of rows already in order compares each row once.** The whole input is one sorted run,
  and the sort finds it in a single pass. The order a file stores its rows in decides what
  sorting them costs, as it decided what skipping them cost in [ch03](#projection-and-filter-pushdown).
- **The top ten cost barely more than reading the rows.** Nearly every row is compared once, with
  the worst of the ten, and loses.
- **The heap's advantage shrinks as k grows.** The chart asks for more and more rows. The top-k's
  comparisons climb with k, and a top-k of every row costs more than a sort.

## Building it

### The top-k

Each row is compared with the worst row kept, the heap's first. It is kept only if it beats that
one, and then it takes the worst row's place. At the end, the few rows kept are sorted:

```{literalinclude} ../python/query_lab/sort.py
:language: python
:start-at: class TopK(Operator):
:end-before: def _listed(
```

```run
experiment: measure
of: sorting
```

Replace the `elif` and the line under it with an `else:` that pushes every row onto the heap and
then pops the worst, and run the panel's report on your edit. The ten rows are the same, and the
comparisons several times as many: every row now climbs into the heap before most are thrown out.

### The sort

The sort holds every row, then sorts them with one comparison function, which counts each call:

```{literalinclude} ../python/query_lab/sort.py
:language: python
:start-at: class Comparisons:
:end-before: def _rows(
```

### The plans

A scan, and a top-k or a sort:

```{literalinclude} ../python/query_lab/plans.py
:language: python
:start-at: def top_orders(
:end-before: def orders_by_amount_within(
```

The book's tests sort by several keys, in both directions, and ask for the top k for k from one
to more than the rows, and require DuckDB's rows in DuckDB's order each time. They check that a
sort of rows already in order compares each row once, and that a top-k never holds more than k
rows.

## Compare

Your top-k beside DuckDB's:

```{include} _generated/top-orders-compare.md
```

- **Both hand up the same ten rows, in the same order.** Ties in the amount would be broken by the
  order id; the query says so, and both engines obey.
- **Both read every row.** Nothing tells a scan which rows will be among the largest, so the
  top-k saves comparisons and memory, not reading. An index on the amount, or a file sorted by
  it, would save the reading too.

## What this cannot tell you

- **What a comparison costs.** Comparing two numbers is cheap; comparing two long strings is not,
  and a real engine compares keys laid out as bytes, often only a prefix of them. The count
  treats every comparison alike.
- **What moving the rows costs.** A sort moves rows as well as comparing them, and wide rows
  cost more to move. That is why DuckDB narrowed its keys, and why it sorts a key and a row's
  position rather than the row. The model moves nothing.
- **How DuckDB sorts.** DuckDB sorts with a radix sort where the keys allow it, which compares
  bytes rather than rows, and sorts in parallel runs that it merges. Its profile reports neither.
- **What happens when the rows do not fit in memory.** The next chapter sorts them anyway.

## What this means for your design

- **Say how many rows you want.** A `LIMIT` turns a sort into a top-k, and saves nearly all of
  its work and memory. Fetching every row and keeping ten in the application pays for the sort
  anyway, as problem 9.3 shows.
- **Store the rows in the order you read them in.** Rows already in order cost one comparison
  each to sort, and a file sorted by the key also lets its statistics skip rows.
- **Sort narrow keys.** Every column in a sort key is compared, and every byte of every row is
  moved. Sort by what you need, and join the wide columns on after, when the rows are few.
- **Beware a large k.** A top-k of thousands keeps thousands of rows and compares each new row
  with them; past a point, a sort is cheaper.

## Key takeaways

:::{div}
:class: takeaways

- **A sort holds every row and compares them many times.** For rows in no order, about the rows
  times their logarithm.
- **Rows already in order are cheap to sort.** The sort finds the run and stops.
- **A `LIMIT` turns a sort into a top-k.** It keeps k rows in a heap and compares most rows only
  with the worst of them.
- **DuckDB narrows its sort keys first.** Every byte in a sort is moved many times.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: sorting_and_top_k
```

**9.1 Merge the runs.** Write `merge_runs`: yield the values of several sorted runs as one sorted
sequence, holding one value from each run at a time. It is the last step of a sort too large for
memory, which the next chapter needs. The graders merge many random runs,
check the result is sorted, and watch each run to make sure you never take a value before you
need it.

**9.2 The top of each customer.** Write `top_per_customer`: each customer's k largest orders. The
graders compare yours with DuckDB's, which numbers each customer's orders by amount and keeps the
first k, for several k.

**9.3 Diagnose the slow page.** No test. A dashboard shows the ten largest orders. Its query has
no `LIMIT`: the application reads the rows the query returns, and keeps the first ten:

```{include} _generated/sort-or-top.md
```

Why does the page cost so much more than the ten rows it shows? What does the engine do that the
application's own limit cannot undo? What would you change, and what would it save in memory and
in comparisons? A good answer compares the two plans' operators, explains what the engine could
not know without the `LIMIT`, and names the change to the query.

## Where to go next

- **Sorting, counted.** Donald Knuth, *The Art of Computer Programming*, volume 3, chapter 5: the
  comparisons every sort needs at least, and the heaps and merges that come close.
- **The sort your engine uses.** Tim Peters,
  [listsort.txt](https://github.com/python/cpython/blob/main/Objects/listsort.txt), on how Python's
  sort finds runs and merges them, and why sorted input costs one comparison a row.
- **DuckDB's sort.** Laurens Kuiper,
  [Fastest Table Sort in the West](https://duckdb.org/2021/08/27/external-sorting.html), on
  sorting keys as bytes, sorting runs in parallel, and writing them to disk.
