---
title: Partitioning and shuffle
---

(partitioning-and-shuffle)=
# Partitioning and shuffle

## The question

When a table is spread over many machines, what must move between them to answer a query, and
how much?

[ch14](#parallelism-on-one-machine)'s workers shared one machine's memory: a worker's table of
groups was a few lines of code away from the one that combined them. Across machines, every row
that must meet another row on a different machine is sent over the network. This chapter counts
those bytes, for an aggregate and a join, each done two ways.

## Observe

An aggregate needs every row of a group in one place, and a join every row with the same key. A
cluster puts them there by hashing the key: each machine owns the keys whose hash, modulo the
number of machines, is its own number. DuckDB can compute where each row would go, with its own
hash, for four machines:

```{include} _generated/partitions.md
```

1. **The customers spread evenly.** Each machine would own about a quarter of them. A hash sends
   each key to a machine without regard for its value, so a thousand different keys fall into
   four nearly equal heaps.
2. **The orders do not.** One machine would receive twice as many as another. A few customers
   place many of the orders, and a hash sends all of one customer's orders to the same place.
   That is [ch16](#skew)'s subject; here it is a warning.
3. **Nothing has moved yet.** The rows start wherever the table's files happen to be. Getting
   each to the machine that owns its key is the cost this chapter counts.

Each machine's share of a table is a partition. Sending every row to the machine that owns its
key is a **shuffle**. Sending a copy of a whole, small table to every machine instead is a
**broadcast**.

## Predict, then measure

Your engine simulates four machines, called nodes: the orders' row groups dealt out to them in
turn, the customers on one. Only a shuffle or a broadcast moves rows, and each counts the bytes it
sends: the Arrow IPC bytes of every row that leaves its node, the book's `bytes_shuffled`
counter.

Predict the bytes shuffled by four plans: orders per customer, shuffling every order to its
customer's node; the same in two phases, each node aggregating its own orders before sending
only the partial counts and sums; the orders joined with their customers' countries, shuffling
both tables; and the same join, broadcasting the customers.

```lab
experiment: measure
of: shuffle
```

The panel draws what your engine counted when the book was built. Its button runs the same nodes
again in your browser.

- **Shuffling every order sends most of them.** Three quarters of the orders are on a node that
  does not own their customer, and go.
- **Two phases send a fraction of that.** Each node first reduces its orders to one row for each
  customer it saw. Only those rows travel.
- **The broadcast sends the customers three times, and the orders not at all.** The customers are
  small; a copy each is cheaper than moving the orders.
- **The chart adds nodes.** A broadcast sends one more copy for every node, and grows without
  limit. A shuffle's cost approaches the size of the tables. Past a point, the shuffle wins.

## Building it

### Where a key belongs

Every node computes the same hash of a key, ch07's, and so agrees on where the key belongs:

```{literalinclude} ../python/query_lab/distributed.py
:language: python
:start-at: def node_of(
:end-before: def shuffle(
```

### The shuffle

A node splits its rows by the node each belongs to, keeps its own, and sends the rest. The bytes
of every piece sent are counted:

```{literalinclude} ../python/query_lab/distributed.py
:language: python
:start-at: def shuffle(
:end-before: def broadcast(
```

```run
tests: test_distributed.py
select: shuffle
```

Change `if there != here:` to `if True:`, so that a row kept on its own node is counted as sent,
and run the engine's tests on your edit: a cluster of one node now sends bytes to itself, and the
test that says it sends nothing fails.

### Two phases

The two-phase aggregate runs ch07's aggregate on each node's own orders, shuffles those partial
results, and aggregates again: the counts and sums of a customer's partials, added together:

```{literalinclude} ../python/query_lab/distributed.py
:language: python
:start-at: def aggregate_in_two_phases(
:end-before: COUNTRY =
```

### Two joins

A shuffle join sends both sides by the join key, so each node joins its own keys with ch08's hash
join. A broadcast join leaves the large side where it is, and gives every node the small one
whole:

```{literalinclude} ../python/query_lab/distributed.py
:language: python
:start-at: def join_by_shuffle(
```

## Compare

DuckDB runs on one machine and never shuffles, so there is no count of its to compare. The
comparison is of the rows: the book's tests run both aggregates and both joins on the simulated
nodes, and require DuckDB's rows from each. The partitions DuckDB's hash chose and the ones
your nodes' hash chose differ, since the two hashes do, but both are uneven for the orders in the
same way, for the same reason.

## What this cannot tell you

- **How long the bytes take.** A network moves bytes at a rate, with a delay per message, and
  machines share it. Bytes are what a plan controls; the time follows from the network.
- **What the pieces cost.** Each piece sent carries a header, and many nodes make many small
  pieces. The counter includes the headers, which is why a shuffle's bytes grow a little with the
  nodes even when the rows do not.
- **What a real cluster does on failure.** A node that dies mid-shuffle loses what it held. The
  chapter after next, [ch17](#stages-and-distributed-execution), counts how engines recover.

## What this means for your design

- **Aggregate before you move.** Two-phase aggregation sends a row per group per node, not a row
  per input row. Engines do this for you when the groups are few; problem 15.3 shows when it does
  not pay.
- **Broadcast the small side.** A dimension table joined to a large fact table is cheapest copied
  to every node. Distributed engines choose it below a size you can usually set.
- **Partition tables by the keys you join and group on.** Data already on the node that owns its
  key need not move. Problem 15.1 checks for it.
- **Mind the skew.** A hash spreads keys evenly, not rows. A popular key sends all its rows to one
  node.

## Key takeaways

:::{div}
:class: takeaways

- **Rows must meet to be grouped or joined.** Across machines, meeting means sending.
- **A shuffle sends each row to the node that owns its key.** Most rows move.
- **Two phases shrink what moves.** Aggregate locally, send the partials.
- **A broadcast copies a small table everywhere.** Cheap for few nodes and a small table; a
  shuffle wins as either grows.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: partitioning_and_shuffle
```

**15.1 Already in place.** Write `already_placed`: whether every row of a partitioned table is on
the node that owns its key, so a shuffle on that key would send nothing. The graders check your
answer against what a shuffle sends, on tables placed by row group and tables already shuffled.

**15.2 Broadcast or shuffle?** Write `choose_join`: from the two sides' bytes and the number of
nodes, which join sends less. The graders run both joins on the simulated nodes, with all the
customers and with only the enterprise ones, and check your choice was not the dearer by more than
a quarter.

**15.3 Diagnose the dear aggregate.** No test. A colleague made every aggregate run in two
phases, and one report got slower:

```{include} _generated/unique-keys.md
```

Why do two phases send so little for the customers and more than a shuffle for the orders? What
does a partial aggregate hold for a key that appears once? When should an engine skip the first
phase, and what could it look at, before running, to decide? A good answer compares the groups
with the rows on each node, and names ch13's estimates as the way to know in advance.

## Where to go next

- **Distributed joins.** Goetz Graefe, *Encapsulation of Parallelism in the Volcano Query
  Processing System*, SIGMOD 1990: the exchange operator, which hides the shuffle behind the same
  interface as every other operator.
- **Aggregation across machines.** Jeffrey Dean and Sanjay Ghemawat, *MapReduce: Simplified Data
  Processing on Large Clusters*, OSDI 2004: map, shuffle and reduce, with the combiner as the first
  phase.
- **A real engine's choice.** Apache Spark's documentation on
  [join strategy hints](https://spark.apache.org/docs/latest/sql-performance-tuning.html), and its
  broadcast threshold.
