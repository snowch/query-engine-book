---
title: Expressions and vectorised kernels
---

(expressions-and-vectorised-kernels)=
# Expressions and vectorised kernels

## The question

What does it cost to compute an expression for every row, and why do engines work a batch at a
time?

Part II made your engine read less. What it does read, it has to compute. Every condition in a
`WHERE` and every column in a `SELECT` is evaluated for every row that reaches it, and from
[ch01](#the-plan-is-the-map) on, your operators have done that with kernels from
`pyarrow.compute`, a whole column at once, without asking what the alternative would cost. This
chapter builds the alternative, a row at a time, and counts the difference in the two places it
shows: the work of deciding what to run, and the work the processor does for each value.

## Observe

The query computes a price with tax on the orders whose unit price is over a hundred, and whose
quantity is over two, written clumsily on purpose:

```{literalinclude} ../queries/with_tax.sql
:language: sql
```

DuckDB's plan, from `EXPLAIN`:

```{include} _generated/with-tax-plan.md
```

1. **DuckDB computed the constants before it ran anything.** The query says `50 * 2`; the filter
   says `100.0`. Working out every part of an expression that depends on no column, once, when
   the query is planned, is **constant folding**.
2. **It moved a sum to the other side.** `quantity + 1 > 3` became `quantity > 2`, a comparison
   of a column with a constant, and so a test the scan can push down, as in
   [ch03](#projection-and-filter-pushdown).
3. **It made the types explicit.** `amount / quantity` became `amount / CAST(quantity AS
   DOUBLE)`: dividing always gives a double, so the whole number is converted first.

Each condition and each computed column is an **expression tree**: the leaves are columns and
constants, and each inner node is an operator applied to the values of the nodes below it.
DuckDB rewrote the trees, then ran what was left, a few thousand values at a time.

## Predict, then measure

A filter must decide, for every row, whether to keep it. Code that decides does so with a
branch: an `if` that jumps one way or the other. A processor does not wait to learn which way a
branch goes. It keeps a **branch predictor**, which guesses from the way the branch went before,
and starts on the guessed path at once. A right guess costs nothing. A wrong guess, a
**misprediction**, throws away the work started on the wrong path. The book's model of a
predictor keeps a two-bit counter for each branch, which moves towards "taken" each time the
branch is taken and back each time it is not.

Your engine can find the rows that pass a test in two ways. With a branch, it asks `if` of each
value and appends the position when the test passes. Without one, it writes every position to
the next free slot and moves the slot on by the test's result, one or nought, so the value
decides what is kept and never which instruction runs next.

Predict the mispredictions of three cases on the orders in date order. First, a test on the date
that keeps the first half of the year, with a branch. Second, a test on the amount that keeps
about half the rows, scattered at random through the file, with a branch. Third, the same test
without one.

```lab
experiment: branches
column: amount
```

The panel draws what your engine and the model counted when the book was built. Its button runs
the same kernels again in your browser.

- **The same test, run the same way, is cheap on a run and dear at random.** On the date, the
  branch went one way for half the file and the other way for the rest, and the predictor was
  wrong only where it turned. On the amount, the branch went either way at random, and the
  predictor was wrong about half the time.
- **Without a branch, the data cannot fool the predictor.** Only the loop's own branch is left,
  and it goes the same way every time but the last.
- **The worst case is a test that keeps about half.** The curve under the cases runs the random
  test at thresholds from nearly every row to none. A test that keeps almost everything or
  almost nothing is predicted well with a branch, because it nearly always goes the same way.

## Building it

### The tree

An expression is one of three things: a column, a constant, or an operator applied to other
expressions. Your engine has no parser yet, so the plan writes the trees out:

```{literalinclude} ../python/query_lab/expressions.py
:language: python
:start-at: # An expression is a tree of three kinds of node.
:end-before: def _divide(
```

### A row at a time

The obvious evaluator walks the tree for each row: look at the node, decide what it is, compute
its arguments, apply its operator to one value. Every decision is made again for every row:

```{literalinclude} ../python/query_lab/expressions.py
:language: python
:start-at: def evaluate_row(
:end-before: def nodes(
```

### A batch at a time

The evaluator your engine uses walks the tree once per batch instead. At each operator node it
calls a kernel, which applies the operator to every value of the batch in a loop compiled ahead
of time, with no decision about the tree inside it. Evaluating a batch at a time is
**vectorised execution**:

```{literalinclude} ../python/query_lab/expressions.py
:language: python
:start-at: def evaluate(
:end-before: def evaluate_row(
```

Both evaluators count `dispatches`, the nodes they visit. Given a vector unit, both also count
the instructions their operators would run. A processor's vector instructions, **SIMD** (single
instruction, multiple data), apply one operation to several values at once, one in each **lane**
of a wide register. A kernel over a whole array fills every lane; code that computes one value at
a time uses one lane and leaves the others idle:

```{literalinclude} ../python/query_lab/cpu.py
:language: python
:start-at: class VectorUnit:
:end-before: # The two ways to find which rows pass a test.
```

The query's two trees, evaluated over the orders a row at a time and in batches of several
sizes:

```{include} _generated/batch-sizes.md
```

- **A row at a time, the evaluator decides far more often than it computes.** It visits every
  node of both trees for every row, constants included.
- **Batches divide the decisions by their size.** A batch of a few thousand rows makes one
  decision per node for all of them.
- **Batches fill the lanes.** One value at a time uses one lane of each instruction. Even small
  batches use nearly every lane, and the instructions fall by the number of lanes.
- **Past a few thousand rows, larger batches save almost nothing more.** The decisions are
  already few.

### The two kernels

The predictor the panel ran:

```{literalinclude} ../python/query_lab/cpu.py
:language: python
:start-at: class Predictor:
:end-before: def counters(self)
```

The two ways to find the rows that pass, the second with no branch on the data:

```{literalinclude} ../python/query_lab/cpu.py
:language: python
:start-at: def select_with_branch(
```

```run
experiment: branches
column: amount
```

Give the kernel without a branch an `if` of its own, and run the panel's report on your edit: its
mispredictions come back.

### The plan

The plan is chapter 1's shape: a scan, a filter and a projection. The filter and the projection
evaluate the query's trees exactly as it writes them, because your engine has no planner yet to
fold them or move them into the scan:

```{literalinclude} ../python/query_lab/plans.py
:language: python
:start-at: WITH_TAX_WHERE = Call(
:end-before: #: Each plan, by the query file it answers.
```

The book's tests evaluate many random trees both ways and require the same values, and hold the
counters to the model's rules: `k` nodes over `r` rows make `k` times `r` dispatches a row at a
time, and the kernel without a branch mispredicts at most twice.

## Compare

Your plan beside DuckDB's:

```{include} _generated/with-tax-compare.md
```

- **Both hand up the same rows, with the same prices.** Folding `1 + 20 / 100` changes when the
  constant is computed, not what it is.
- **DuckDB's filter tests fewer rows.** It moved `quantity > 2` into its scan, so its filter
  sees only the rows the scan kept. Your filter tests every row with the whole tree, constants
  and all. Part IV builds the planner that makes these rewrites.
- **DuckDB works a vector at a time.** Its operators pass vectors of a fixed size, a couple of
  thousand values, small enough that a vector's columns stay in the cache between operators, as
  [ch02](#batches-in-memory) measured. Its source shows comparison kernels that find the passing
  rows as your kernel without a branch does: they write every position and move on by the result.
- **DuckDB does not report its dispatches, branches or instructions.** Nor does any engine's
  profile. The counts are your engine's and the model's.

## What this cannot tell you

- **What a misprediction costs in time.** The model counts wrong guesses, not the cycles each
  one wastes, which depend on the processor. A modern processor loses on the order of a dozen or
  more cycles to each.
- **How a real predictor guesses.** Real predictors remember the history of many branches
  together and would learn some patterns the two-bit counter cannot, such as a branch that
  alternates. Random data fools them all.
- **Whether a compiler used vector instructions.** The vector unit assumes every kernel fills its
  lanes. A real kernel does only if the compiler, or its author, made it so; the model gives
  every value eight bytes, where narrower types would fit more to a register.
- **How fast Python is.** Your evaluator's dispatches are Python function calls, far dearer than
  the virtual calls a compiled engine makes. The counts compare the two ways of evaluating, not
  your engine with DuckDB.
- **What the batch size does to memory.** The model gives a batch of every row the fewest
  decisions. A real engine keeps its batches small enough to stay in the cache, which the
  evaluator's counters do not see.

## What this means for your design

- **Let the planner fold what it can, and write predicates it can push.** `quantity > 2` can
  reach the scan; `quantity + 1 > 3` can only if the planner rewrites it. Write the column alone
  on one side where you can, and check the plan.
- **Mind the tests that keep about half at random.** A filter on a column in random order, which
  keeps about half, is the worst case for a branch. Engines avoid it with kernels that do not
  branch on the data; your own code, in a user-defined function, may not.
- **Sort by what you filter on, for the processor too.** The same test on sorted data made a run
  the predictor learned at once. Sorting helped the scan's statistics in
  [ch03](#projection-and-filter-pushdown); it helps the filter's branches as well.
- **Prefer engines and functions that work a batch at a time.** A user-defined function that
  receives one row per call brings back the row-at-a-time evaluator, with a decision per row and
  one lane per instruction. One that receives an Arrow array does not.

## Key takeaways

:::{div}
:class: takeaways

- **An expression is a tree, and a planner rewrites it before it runs.** DuckDB folded the
  constants and moved a sum so the scan could test it.
- **A row at a time, every node is decided for every row.** A batch at a time, once per batch.
- **Batches fill the vector lanes.** One value at a time leaves most of each instruction idle.
- **A branch on random data is guessed wrong about as often as it goes the rarer way.** The same
  test on sorted data, or written without a branch, is almost never guessed wrong.
- **The counts are a model.** They show which way costs more and why, not how many nanoseconds.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: expressions_and_vectorised_kernels
```

**6.1 Fold the constants.** Write `fold`: the same tree with every part that depends on no column
computed once and replaced by a constant, as DuckDB did to `50 * 2`. The graders fold the
chapter's trees and many random ones, then evaluate both over the orders and require the same
values, and require that no part without a column is left, and that every column stays.

**6.2 Always wrong.** Write `always_wrong`: a run of outcomes of one branch that the two-bit
predictor gets wrong every time, from whichever of its four states it starts in. The graders run
the book's predictor on your outcomes, from each state, for many lengths.

**6.3 Diagnose the slow filter.** No test. A colleague finds that the chapter's random test,
`amount` over its middle value, filters much faster once the orders are sorted by amount, though
it keeps the same rows and compares the same values:

```{include} _generated/sorted-branches.md
```

Why does the order of the rows change the cost of the same comparisons? What does the kernel
without a branch do on each order, and why? The colleague proposes to store the orders by amount
from now on. What would that cost the queries of [ch03](#projection-and-filter-pushdown) and
[ch04](#statistics-and-pruning), and what would you propose instead? A good answer explains the
predictor's counter on each order, and weighs the filter's branches against the scan's
statistics.

## Where to go next

- **Where vectorised execution comes from.** Peter Boncz, Marcin Zukowski and Niels Nes,
  *MonetDB/X100: Hyper-Pipelining Query Execution*, CIDR 2005: the paper that introduced
  evaluating a vector of values per call, and measured what a tuple at a time costs.
- **Branches in database kernels.** Kenneth Ross, *Selection Conditions in Main Memory*, ACM
  TODS 2004: filters with and without branches, and how to choose between them by selectivity.
- **Vectorised against compiled.** Timo Kersten and others, *Everything You Always Wanted to Know
  About Compiled and Vectorized Queries But Were Afraid to Ask*, VLDB 2018: the other way to
  remove the decisions, by compiling the whole query, measured against vectors.
- **DuckDB's own kernels.** DuckDB's [source](https://github.com/duckdb/duckdb), in
  `src/include/duckdb/common/vector_operations/`, holds the loops that apply one operator to a
  vector, and the select loops that write every position and move on by the result.
- **Arrow's kernels.** The [Arrow compute documentation](https://arrow.apache.org/docs/cpp/compute.html)
  lists the kernels your engine calls, and how they handle nulls and types.
