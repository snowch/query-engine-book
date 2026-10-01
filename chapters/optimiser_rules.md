---
title: Optimiser rules
---

(optimiser-rules)=
# Optimiser rules

## The question

Which rewrites of a plan save work whatever the data, and what does each one save?

[ch11](#from-sql-to-a-logical-plan) built the plain plan: correct, and reading the whole of every
file it names. Every plan the book wrote by hand before it was cheaper, and each was cheaper in a
way a person could see from the query's text alone: read only these columns, test this condition
in the scan, keep ten rows instead of sorting all of them. This chapter teaches the planner to see
the same things, as rules that rewrite the logical plan, and counts what each rule saves.

## Observe

The query is ch11's, the enterprise orders:

```{literalinclude} ../queries/enterprise_orders.sql
:language: sql
```

DuckDB can turn its rules off by name. Here it runs the query with every rule, then without the
rule that moves filters down the plan, then without the rule that removes columns nothing uses:

```{include} _generated/enterprise-orders-rules-off.md
```

1. **Without `filter_pushdown`, the segment is tested above the customers' scan.** The scan hands
   up every customer, and a filter drops most of them. The bytes grow too: the scan must now read
   the `segment` column, to hand it up to the filter.
2. **Without `unused_columns`, nothing changes.** DuckDB's binder asked each scan for only the
   columns the query names in the first place, so this rule had nothing to remove here. It
   matters after other rules have run, when a column that was needed no longer is.
3. **Some of the moving happens anyway.** Even without `filter_pushdown`, both conditions sit
   below the join, on their own tables. DuckDB builds its joins in a later step that places
   conditions too, and turning one rule off does not undo the other's work.

A rule that rewrites a plan into one that gives the same rows for less work is a **rewrite
rule**. The part of the planner that applies its rules, and later chooses between plans, is its
**optimiser**. The rules here share one property: each makes the plan cheaper, or leaves it as it
was, whatever the data holds. They can be applied without knowing anything about the files.

## Predict, then measure

Your planner gets three rules. The first moves each condition down the plan as far as its
columns allow: below a join to the table it reads, and into the scan if it compares a column with
a constant. The second has each table read only the columns something above it uses. The third
turns a sort with a limit above it into ch09's top-k.

Predict the bytes the enterprise orders read with the first rule alone, the second alone, and
both. The panel shows the plain plan's bytes beside each.

```lab
experiment: measure
of: rules
```

The panel draws what your engine counted when the book was built. Its button runs the same plans
again in your browser.

- **Moving the filters saves no bytes.** The customers' file is one row group, so testing the
  segment in the scan skips nothing, and the orders' condition is an expression the scan cannot
  test. But far fewer rows reach the join: the counters show it.
- **Pruning the columns saves bytes, and no rows.** Each scan reads the columns the query uses,
  and hands up every row it did before.
- **Together they save both.** Each rule saves a different thing, and the rules do not get in
  each other's way.

Time the same four plans, run by your engine in your browser:

```timed
of: rules
```

- **Time follows the bytes here, more than the rows.** Your engine spends most of a plan's time
  decoding in its scans, as [ch01](#the-plan-is-the-map)'s profile showed, so pruning the columns
  saves the most, and moving the filters, which leaves the scans as they were, saves little.
- **Both rules make the quickest plan.** In an engine whose joins cost more than its scans, the
  rows the filters keep from the join would be worth more; the counters say what each rule saves,
  and the time what that is worth in this engine.

## Building it

### Conditions, as far down as they go

A condition joined by `AND` holds only where each of its parts holds, so each part can be tested
on its own, anywhere below the filter that its columns are available. Each such part is a
**conjunct**. The rule splits every filter into its conjuncts and pushes each down, one step at a
time:

```{literalinclude} ../python/query_lab/rules.py
:language: python
:start-at: def push_filters(
:end-before: def _in_scan(
```

```run
experiment: measure
of: rules
```

Delete the `case Join():` branch and the lines under it, so that no condition passes a join,
and run the panel's report on your edit: every row of both tables reaches the join again, and the
panel says your edit changed the answer.

A conjunct whose columns are all on one side of a join goes to that side. One that reads both
sides, such as a condition on a customer's segment or an order's amount, stays above the join.

### Into the scan

At a table, the conjunct goes into the scan itself if it compares one column with a constant,
which is what ch03's scan can test, and skip row groups with. Anything else stays as a filter
directly above the scan:

```{literalinclude} ../python/query_lab/rules.py
:language: python
:start-at: def _in_scan(
:end-before: # Columns, pruned.
```

### Columns, from the top down

The second rule walks down from the top, carrying the columns that the steps above need. Each
step adds what it reads itself: a filter its condition's columns, a join its keys, a sort its
keys. At a table, the scan keeps only the columns in the set:

```{literalinclude} ../python/query_lab/rules.py
:language: python
:start-at: def prune_columns(
:end-before: # A sort and a limit, as a top-k.
```

A `count(*)` needs no column at all, but a scan counts rows by reading something, so it keeps one.

### A sort and a limit

The third rule is the smallest. A limit directly above a sort becomes one step that keeps the
first rows, which the planner runs as ch09's top-k:

```{literalinclude} ../python/query_lab/rules.py
:language: python
:start-at: def top_k(
:end-before: #: The rules, in the order
```

Your planner's plan for the enterprise orders, after all three rules:

```{include} _generated/enterprise-orders-rewritten.md
```

## Compare

Every plan the book wrote by hand, beside the plan your rules make from the text alone:

```{include} _generated/rules-rebuild.md
```

- **The rules rebuild every plan the book wrote by hand.** From ch01's filter and projection to
  ch09's top-k and this part's join, the bytes are the same, from nothing but the query's text.
- **Except the page index.** ch04's scan read the page index because its plan told it to. That
  is a way of scanning a file, not a rewrite of the plan, and the rules leave scans as ch03 built
  them. DuckDB 1.1.2 makes the same choice, as ch04 found.
- **Every rewritten plan gives DuckDB's rows.** The book's tests run each query through all
  three rules and compare the rows with DuckDB's.

## What this cannot tell you

- **How many rules a real optimiser has.** DuckDB's has dozens, applied in a fixed order: it
  folds constants, pulls filters up before pushing them down, removes duplicate work, rewrites
  subqueries into joins, and more. Three rules cover the book's queries.
- **Whether the order of rules matters.** For these three, it does not. For a larger set it
  does: one rule can open the way for another, and optimisers apply some rules more than once.
- **What rules cannot see.** No rule here knows how big a table is, how many rows a condition
  keeps, or which side of a join is smaller. Those choices need statistics, which is the next
  chapter's subject.

## What this means for your design

- **Write conditions as a column against a constant.** `quantity > 2` can be tested in the scan
  and used to skip row groups; `quantity + 1 > 3` cannot, unless the optimiser rewrites it, as
  problem 12.1 does. DuckDB rewrote it in ch06; a smaller engine may not.
- **Keep conditions on one table where you can.** A condition that reads two tables waits above
  their join, which sees every pair. Problem 12.3 measures one.
- **Check the plan for your conditions.** `EXPLAIN` shows where each condition ended up: in a
  scan's filters, in a filter above it, or above a join.
- **Do not hand-optimise the text.** Moving a condition next to its table in the `WHERE` clause
  changes nothing: the rules put it there anyway.

## Key takeaways

:::{div}
:class: takeaways

- **An optimiser rewrites the logical plan by rules.** Each rule gives the same rows for less work,
  whatever the data.
- **Filters go down, split into their conjuncts.** Each conjunct stops at the lowest step where its
  columns exist, inside the scan if it compares a column with a constant.
- **Columns are pruned from the top down.** Each scan reads what some step above it uses.
- **Three rules rebuild every plan the book wrote by hand.** Choosing between plans that give the
  same rows by different amounts of work needs more than rules.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: optimiser_rules
```

**12.1 Move the constants.** Write `move_constants`: rewrite `quantity + 1 > 3` as `quantity > 2`,
so that the scan can test it. The graders put your rewrite before the book's rules and check that
every condition they give it reaches the scan, with DuckDB's rows. They also check your rewrite
against the original on every order, for many random conditions, and that it leaves alone what it
cannot move.

**12.2 Across the join.** Write `across_the_join`: a rule that copies a condition on one side's
join key to the other side's key, since the two are equal in every joined row. The graders run it
before `push_filters`, and check that both tables' scans test the key, that the orders' scan hands
up fewer rows, and that the rows are DuckDB's.

**12.3 Diagnose the slow report.** No test. A report wants the orders of enterprise customers, and
every large order whoever placed it, in one query:

```{literalinclude} ../queries/enterprise_or_large.sql
:language: sql
```

Your rules and DuckDB both leave its condition above the join:

```{include} _generated/either-side.md
```

Why can neither move the condition to a table? What does the join do as a result? How would you
write the report so that each condition can reach its own table's scan, and what must you take
care of when you combine the two answers? A good answer explains why a condition joined by `OR`
is not a conjunct, and proposes two queries whose rows are combined without counting an order
twice.

## Where to go next

- **Rules and their order.** Goetz Graefe, *The Cascades Framework for Query Optimization*, IEEE
  Data Engineering Bulletin, 1995: rules as the unit of an optimiser, and how to apply many of
  them.
- **The rules of a real engine.** DuckDB's [source](https://github.com/duckdb/duckdb), in
  `src/optimizer/`: `filter_pushdown.cpp`, `remove_unused_columns.cpp` and `topn_optimizer.cpp`
  are this chapter's three rules, and `optimizer.cpp` lists the order DuckDB applies all of them
  in.
- **Why optimisers are hard.** Viktor Leis and others, *How Good Are Query Optimizers, Really?*,
  VLDB 2015: what goes wrong when rules are not enough, and plans must be chosen.
