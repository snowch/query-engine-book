---
title: Skew
---

(skew)=
# Skew

## The question

What happens when a few keys hold most of the rows, and how can an engine share them out anyway?

[ch15](#partitioning-and-shuffle)'s hash spread the customers evenly over the nodes, and the orders
unevenly. Every order of a customer goes to the node that owns the customer, so a customer who
placed a fifth of the orders sends a fifth of the orders to one node. The others finish and wait.
This chapter measures how much one heavy key costs a cluster, and builds the usual cure.

## Observe

DuckDB counts each customer's orders, and names the heaviest with a sketch that never counts
them all:

```{include} _generated/heavy-customers.md
```

1. **One customer placed nearly a fifth of all orders.** The next placed half as many again, and
   the numbers fall quickly after. The orders' customers were drawn this way on purpose, as real
   customers, products and pages are: a few are far more popular than the rest.
2. **The sketch found the same customers.** `approx_top_k` keeps a small, fixed number of counters
   as it reads, and still names the heaviest keys. An engine can learn which keys are heavy without
   holding a count for every key.
3. **No hash can split one key.** However many nodes there are, the node that owns customer 1
   receives every one of that customer's orders.

A key that holds far more than its share of the rows is a **heavy hitter**, and a distribution of
rows over keys, or over nodes, that is far from even is skew.

## Predict, then measure

Your engine runs ch15's join of the orders and their customers' countries on sixteen simulated
nodes, three ways: shuffled by customer, as ch15 did; with the heaviest customers' orders spread
over several nodes, and their customer rows copied to each; and with the customers broadcast, so
the orders stay where they were read.

Predict the rows the busiest node joins in each. The panel shows an even share beside each.

```lab
experiment: measure
of: skew
```

The panel draws what your engine counted when the book was built. Its button runs the same nodes
again in your browser.

- **Shuffled by customer, one node joins several times its share.** Customer 1's orders all land
  there, with those of the other customers the node owns.
- **Spreading the heaviest customers brings the busiest node close to its share.** Their orders
  now go to several nodes each, and no one node holds a heavy customer whole.
- **The broadcast has no skew at all from the customers.** The orders never move; the busiest
  node is the one that read the most row groups.
- **The chart adds nodes.** An even share halves with every doubling. The busiest node of the plain
  shuffle cannot fall below customer 1's orders, however many nodes there are; the spread one keeps
  falling.

## Building it

### Heavy keys

The engine counts each key's rows in one pass before the join, and calls heavy any key with more
than half a node's even share:

```{literalinclude} ../python/query_lab/skew.py
:language: python
:start-at: def heavy_keys(
:end-before: def send(
```

Problem 16.1 finds them in far less memory, as DuckDB's sketch did.

### Salting

Each order of a heavy customer gets a **salt**, a small number taken from the order itself, its id
modulo the number of nodes to spread over. The salt moves the order along from its customer's node.
Every other order goes where ch15 sent it:

```{literalinclude} ../python/query_lab/skew.py
:language: python
:start-at: def salted(
:end-before: def join_salted(
```

```run
experiment: measure
of: skew
```

Salt every customer, not only the heavy ones, by changing `if k in heavy` to `if True` in both
functions, and run the panel's report on your edit. The busiest node falls a little further, and
every customer's row is now copied to every node: the bytes shuffled climb.

The copies are the price. A heavy customer's row must be on every node its orders went to, or
they would find no match there, so the other side's row for each heavy key is sent to all of
them.

### The join

The salted join sends both sides, each by its own rule, then runs ch08's hash join on every node:

```{literalinclude} ../python/query_lab/skew.py
:language: python
:start-at: def join_salted(
:end-before: def busiest(
```

## Compare

DuckDB runs on one machine and does not salt; its sketch is the part to compare. `approx_top_k`
named the five heaviest customers, and they are the five your engine's exact count calls heaviest.
The book's tests check that the salted join gives DuckDB's rows, on two nodes and on sixteen, and
that salting lightens the busiest node when there are many.

## What this cannot tell you

- **How skew shows in time.** The busiest node's rows set when the join ends, as ch14's busiest
  worker did. How long that is depends on the machine, which the count does not.
- **When salting pays for itself.** Copies of the other side's rows cost bytes, and the heavy keys
  must be known first, which costs a pass or a sketch. For a small skew, neither is worth it.
- **How real engines choose.** Spark's adaptive execution measures the shuffle's partitions as it
  runs, and splits the large ones; others salt only when told to. The simulation salts by rule.

## What this means for your design

- **Expect skew in any key people choose.** Customers, products, pages and places are all popular
  in the same lopsided way. Check the heaviest keys before you partition by one.
- **Aggregate before you shuffle.** ch15's two phases reduce a heavy customer's orders to one row
  per node before anything moves: skew in an aggregate mostly vanishes.
- **Broadcast when one side is small.** A broadcast join moves no rows of the large side, so its
  skew never matters.
- **Mind skew in time as well as in keys.** Partitioning by date sends a report on one month to one
  node. Problem 16.3 shows it.

## Key takeaways

:::{div}
:class: takeaways

- **A hash spreads keys, not rows.** A heavy key sends all its rows to one node.
- **The busiest node sets the pace.** Skew makes one node do several times its share.
- **Salting spreads a heavy key over several nodes.** Its rows get a salt; the other side's row is
  copied to each.
- **Heavy keys can be found cheaply.** A sketch with a few counters names them in one pass.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: skew
```

**16.1 Heavy hitters in little memory.** Write `heavy_hitters`, the Misra-Gries summary: one pass
over the keys, holding at most k counters, that is certain to keep every key with more than a
share of one in k + 1. The graders run it over the orders' customers and over random streams, and
check no heavy key is missed and no count is too high.

**16.2 How far to spread.** Write `fanouts`: for each heavy key, the fewest nodes to spread its
rows over so that none holds more than an even share of them. The graders check each choice is
the smallest that works, and that on many nodes the busiest node is lighter for it.

**16.3 Diagnose the busy month.** No test. A team partitioned the orders by month over twelve
nodes, so that a report on one month reads only one node's rows. Their March report is no faster
than it was on one machine:

```{include} _generated/busy-month.md
```

Why is the table evenly spread and the report not? What did partitioning by month buy the report,
and what did it cost? How would you partition the table so that a report on one month keeps
every node busy, and what would you lose? A good answer separates skew in the data from skew in
the query, and weighs reading less against sharing the work.

## Where to go next

- **Finding heavy hitters.** Jayadev Misra and David Gries, *Finding Repeated Elements*, Science of
  Computer Programming, 1982: the summary of problem 16.1.
- **Skew in joins.** David DeWitt, Jeffrey Naughton, Donovan Schneider and S. Seshadri, *Practical
  Skew Handling in Parallel Joins*, VLDB 1992: sampling for heavy keys, and spreading them.
- **Skew handled as it happens.** Apache Spark's documentation on
  [adaptive query execution](https://spark.apache.org/docs/latest/sql-performance-tuning.html),
  which splits skewed partitions of a shuffle join at run time.
