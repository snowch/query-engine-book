---
title: Statistics, cost and join order
---

(statistics-cost-and-join-order)=
# Statistics, cost and join order

## The question

How does a planner choose between plans that give the same rows, when it cannot run them to
find out which is cheaper?

[ch12](#optimiser-rules)'s rules were safe whatever the data. Some choices are not. Three tables
can be joined in several orders, each join can hold either input, and every choice gives the same
rows for very different work. The planner must choose before it has read a row, so it guesses
how many rows each step will hand up, from what the files say about themselves. This chapter
builds those guesses, uses them to choose an order of joins, and measures how good the guesses
are.

## Observe

The query joins three tables: the orders, their customers, and the customers' countries, keeping
the customers in Asia. It is written in the order a person might write it, orders first:

```{literalinclude} ../queries/asian_orders.sql
:language: sql
```

DuckDB's plan:

```{include} _generated/asian-orders-plan.md
```

1. **DuckDB did not join in the written order.** It joined the customers with the countries
   first, and the orders last. The text joins the orders first.
2. **It held the smaller side of each join.** The lower join builds on the two Asian countries.
   The upper join builds on the lower join's result, a few hundred customers, and streams all
   the orders past it.
3. **Every operator carries an estimate.** Two countries from the region's filter, a few hundred
   customers from the lower join, a few thousand orders from the upper one. DuckDB chose the
   order from these numbers, before reading any row.

A planner's guess at the rows a step will hand up is its cardinality estimate, from
[ch01](#the-plan-is-the-map). A planner turns the estimates into one number for a whole plan,
its cost, and chooses the plan whose cost is least; the rule that computes the number is its
**cost model**. Here the cost of a plan is the rows its joins hand up, added together: rows that
must be made, held or passed on.

## Predict, then measure

Your planner gets estimates from each file's footer: its rows, and each column's smallest and
largest value. It guesses that values are spread evenly between those two, and that conditions
are independent of each other.

Predict the rows each of three plans' joins hand up, added together: the orders joined with the
customers and then the countries, as written; the customers joined with the countries first and
then the orders; and that second order with the orders held rather than the customers. The panel
shows your planner's estimate beside each.

```lab
experiment: measure
of: join_orders
```

The panel draws what your engine counted when the book was built. Its button runs the same plans
again in your browser.

- **The written order makes many times the rows.** The first join pairs every order with its
  customer, all of them, and only the second join drops the orders outside Asia.
- **The smaller join first makes few.** The customers in Asia are found first, and each order
  meets only them.
- **Holding the orders makes the same rows and holds far more.** The build side is ch08's choice,
  and the estimates make it too: the side guessed smaller is held.
- **The estimates were close, and good enough.** A planner does not need the right numbers, only
  the right order between plans. The chart shows where the even-spread guess goes wrong: amounts
  are a quantity times a price, so large amounts are rarer than the range suggests, and the guess
  for `amount > x` is several times too high.

## Building it

### What the footer says

A Parquet footer holds, for each column of each row group, the smallest and largest value and
the count of nulls. The planner reads them once for each file, and keeps the smallest, the
largest and the rows. For whole numbers and dates the range also bounds the number of distinct
values: a column of customer ids from one to a thousand has at most a thousand. For strings, the
footer says nothing about distinct values, and the planner knows only that there are no more of
them than rows.

### Selectivity

The fraction of rows a condition keeps is its selectivity, from [ch01](#the-plan-is-the-map).
The planner guesses it from the column's statistics:

```{literalinclude} ../python/query_lab/cost.py
:language: python
:start-at: def _fraction(
:end-before: def _minus(
```

A range keeps the part of the column's range it covers. An equality keeps one distinct value's
share, if the planner knows how many there are, and otherwise a fixed guess of a fifth, as
DuckDB's does. Conditions joined by `AND` are multiplied, as if knowing one told you nothing
about the other: the **independence assumption**.

### Estimates, step by step

The estimates travel up the plan. A scan's rows are the file's rows times its conditions'
selectivities; a filter's, its input's times its condition's. A join's are the product of its
inputs, divided by the number of distinct keys, as if every key on the side with fewer found its
matches on the other:

```{literalinclude} ../python/query_lab/cost.py
:language: python
:start-at: def estimate(
:end-before: def joined_rows(
```

```run
experiment: measure
of: join_orders
```

Change the join's estimate to divide by the larger bound, `max`, in place of `min`, and run the
panel's report on your edit. The estimates for the customers and the countries collapse to a
handful of rows: the strings' bound is the customers' thousand, not the countries' twelve.

### The order of joins

With estimates, the planner can compare orders without running them. The rule takes a tree of
joins apart into its inputs and the pairs of keys that join them, then builds the cheapest plan
for every set of inputs from the cheapest plans for its parts, smallest sets first. This is
**dynamic programming**: each set's best plan is found once, and every larger set reuses it:

```{literalinclude} ../python/query_lab/cost.py
:language: python
:start-at: def join_order(
:end-before: def _flatten(
```

Each join it builds holds the input guessed smaller, so the rule chooses ch08's build side too.

## Compare

Each join of the chosen plan, your planner's estimate and DuckDB's beside the rows each made:

```{include} _generated/asian-orders-estimates.md
```

- **Both planners chose the same order and the same build sides.** From the footer alone.
- **Both estimates were a little low for the orders.** The customers in Asia placed more orders
  than their share of customers. The customer ids are skewed: a few customers place many of the
  orders, and nothing in the footer says which.
- **Your planner guessed the countries from their range; DuckDB from its own defaults.** Both
  arrived near the rows the join made, for different reasons.

## What this cannot tell you

- **What DuckDB keeps about its own tables.** For a file it reads, DuckDB knows what the footer
  says. For a table in its own storage it keeps distinct counts, sketched with HyperLogLog, and
  estimates better.
- **Whether the cost counts the right things.** Rows handed up is a simple cost. Real optimisers
  weigh reading, hashing and holding differently, and a join that spills costs more than its
  rows say.
- **How far dynamic programming goes.** The number of sets of inputs doubles with each table.
  Planners switch to cheaper searches past a dozen or so tables, and DuckDB does so too.

## What this means for your design

- **Estimates are made from what the files say.** Footers with statistics, files sorted so their
  ranges are narrow, and table formats that keep distinct counts all make better plans.
- **Beware correlated conditions.** Two conditions on related columns keep far fewer or far more
  rows than their product suggests. Problem 13.3 shows one.
- **Beware skew.** A key that a few values dominate breaks every even-spread guess. The skew
  chapter in Part V comes back to it.
- **Read the estimates in `EXPLAIN`.** When a plan looks wrong, compare its estimates with the
  rows the profile counted. The step where they part is where the planner went wrong.

## Key takeaways

:::{div}
:class: takeaways

- **A cost-based planner chooses between plans that give the same rows.** It cannot run them, so it
  estimates.
- **Estimates come from statistics and assumptions.** Values spread evenly, conditions
  independent, keys that match.
- **Dynamic programming finds the cheapest order of joins.** The best plan for each set of tables,
  from the best plans for its parts.
- **An estimate need only be good enough to order plans.** When it is not, the plan is wrong for
  reasons the query's text never shows.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: statistics_cost_and_join_order
```

**13.1 A histogram.** The chart showed the even-spread guess failing on the amounts. Write
`histogram`, the bounds of an **equal-depth histogram** built from a sample of a column, and
`fraction_above`, the fraction of values above `x` it estimates. The graders build one from a
sample of the orders' amounts, and require your estimate to be close to the count for every
amount they try.

**13.2 The best order.** Write `best_order`: given each table's rows and each join's selectivity,
the order of joins, one table at a time, whose joins hand up the fewest rows. The graders try
every order of up to six tables to find the cheapest, and compare yours with it.

**13.3 Diagnose the bad estimates.** No test. Five conditions on the orders, the rows your
planner and DuckDB estimate each keeps, and the rows it keeps:

```{include} _generated/misestimates.md
```

For each condition, which assumption made the estimates wrong, or right? What statistic would
have fixed each one? And if each condition were on the build side of a join, which estimate would
lead a planner to hold the wrong side? A good answer names the even spread, the missing distinct
count, independence and skew, and proposes a histogram, a distinct count, statistics over two
columns together, and a list of the most common values.

## Where to go next

- **Cost-based planning.** Patricia Selinger and others, *Access Path Selection in a Relational
  Database Management System*, SIGMOD 1979: selectivity, cost, and dynamic programming over join
  orders, as this chapter builds them.
- **How wrong estimates are.** Viktor Leis and others, *How Good Are Query Optimizers, Really?*,
  VLDB 2015: estimates against counts on real data, and what the errors cost.
- **Searching larger spaces.** Guido Moerkotte and Thomas Neumann, *Dynamic Programming Strikes
  Back*, SIGMOD 2008: the join-order search DuckDB's planner builds on.
- **DuckDB's estimates.** DuckDB's [source](https://github.com/duckdb/duckdb), in
  `src/optimizer/join_order/`, the estimator and the search.
