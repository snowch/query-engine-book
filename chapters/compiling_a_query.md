---
title: Compiling a query
---

(compiling-a-query)=
# Compiling a query

## The question

What does an engine save by turning a query into code before it runs it, and what does it give up?

[ch06](#expressions-and-vectorised-kernels) evaluated an expression tree two ways: a row at a time,
visiting every node for every row, and a batch at a time, visiting every node once a batch and
running a kernel over the whole batch at each. The second is how DuckDB runs. Some engines do
neither: before they read a row, they write code for the query, compile it, and run that. This
chapter builds a compiler for a pipeline, and counts what it saves the interpreter and what it
costs.

## Observe

ch01's query tests the status and a unit price, and returns the unit price:

```{literalinclude} ../queries/returned_unit_price.sql
:language: sql
```

DuckDB's plan for it:

```{include} _generated/returned-unit-price-explain.md
```

The book ran the query again with the division replaced by a function that counts how often
DuckDB calls it, and how many values it computes:

```{include} _generated/unit-price-calls.md
```

1. **The unit price is computed twice.** The filter computes it for every returned order, to test
   it, and the projection computes it again for every order the filter kept. Each operator
   evaluates its own tree, and neither knows the other has the value.
2. **A few calls computed them all.** DuckDB calls the function once for each vector, a batch of
   rows, not once a row: it is ch06's batch at a time.
3. **Between the two, the value was written down and thrown away.** The filter's kernel wrote the
   unit prices into a vector, tested them into another, and kept the rows; the projection then
   began again from the columns.

Writing code for a query from its plan, then compiling and running that code in place of
interpreting the plan, is **query compilation**.

## Predict, then measure

Your engine runs the same pipeline three ways, over the same batches: interpreted a row at a time
and a batch at a time, as in ch06, and compiled into one loop. Each counts the nodes of a tree it
visits as the rows run, the instructions of ch06's vector unit, and the bytes it writes into
arrays: every kernel's result, every batch a filter keeps, and the result.

Predict the bytes each way writes. The panel shows the bytes of the result beside each.

```lab
experiment: measure
of: compiling
```

The panel draws what your engine counted when the book was built. Its button runs the same three
ways again in your browser.

- **A row at a time writes only the result.** Each value passes from node to node in a variable.
  It pays in nodes visited: every node, for every row that reaches it.
- **A batch at a time writes several times the result.** Every node's kernel writes an array, and
  each filter writes a batch of the rows it keeps, for the next operator to read. It visits each
  node once a batch.
- **The compiled loop writes only the result and visits nothing.** The compiler visited each node
  once, before any row was read.
- **The compiled loop runs several times the instructions of a batch at a time.** It computes one
  value at a time, where a kernel fills every lane of the vector unit. That is what it gives up.
- **The chart lengthens the computed column.** Every operation adds an array to the interpreter's
  bytes; the compiled loop's stay where they were.

Now time the three ways, none of them counting as it runs, in your browser:

```timed
of: compiling
```

- **The compiled loop beats interpreting a row at a time.** Both handle one row at a time in
  Python; the loop no longer walks a tree to do it. The nodes it stopped visiting are the time it
  saved.
- **A batch at a time beats both, by far.** Its kernels are pyarrow's, compiled ahead of time to
  machine code, and the compiled loop is still Python, run by an interpreter. The bytes the
  kernels write cost less than the interpreter's work on every value. Compiling pays when it
  writes machine code, as HyPer and Umbra do; compiled into Python, it cannot catch a native
  kernel.

## Building it

### An expression as Python

The compiler writes each node of a tree as the Python for it, applied to one row's values: a
column read at row `i`, an operator written out between its arguments:

```{literalinclude} ../python/query_lab/compile.py
:language: python
:start-at: def python(
:end-before: @dataclass
```

### The loop

The compiler walks the pipeline's trees once. Each filter becomes an `if` that skips the row, and
each output column a value appended to the result. A value two trees share is computed once, into
a local variable, where the first tree needs it:

```{literalinclude} ../python/query_lab/compile.py
:language: python
:start-at: def generate(
:end-before: def _operations(
```

```run
experiment: measure
of: compiling
```

Stop it sharing, changing `uses[expr] > 1` to `False`, and run the panel's report on your
edit: the compiled loop's instructions rise by a division for every order it returns, the second
unit price DuckDB computed too.

For ch01's query, it writes:

```{include} _generated/generated-pipeline.md
```

One loop, no kernels, and the unit price computed once, in `v0`, for the filter and the output
alike. A row that fails the status test costs one comparison and no more.

### Compiling and running it

Python compiles the source into a function once, and the function runs once a batch:

```{literalinclude} ../python/query_lab/compile.py
:language: python
:start-at: def compiled(
:end-before: def interpreted(
```

The book's tests run four of the book's queries all three ways, and require DuckDB's rows from
each; they check the generated code is one loop, and computes a shared value once.

## Compare

- **DuckDB interprets, a vector at a time.** Its filter and its projection each evaluate their own
  trees, and it computed the unit price twice for the rows that reached the projection. Your
  compiled loop computed it once.
- **DuckDB chose vectors on purpose.** A kernel is compiled once, ahead of time, for every type it
  takes, and runs over a whole vector in a tight loop the processor can fill every lane of. The
  per-vector decisions cost little when a vector holds thousands of rows. DuckDB's
  [source](https://github.com/duckdb/duckdb) shows both halves: `src/execution/expression_executor.cpp`
  walks a tree once for each vector, and `src/include/duckdb/common/vector_operations/binary_executor.hpp`
  is the loop a binary operator's kernel runs.
- **Other engines compile.** HyPer and Umbra write machine code for each pipeline, as your
  compiler writes Python. Apache Spark's whole-stage code generation writes Java for each stage of
  a plan and compiles it.
- **Neither wins everywhere.** Compiled loops keep values in registers and win when a query
  computes a lot on each row; vectorised kernels fill vector lanes and, as Kersten and others
  measured, hide the processor's waits for memory better, and win when a query mostly probes hash
  tables.

## What this cannot tell you

- **How long compiling takes.** Python compiles a small function quickly. An engine that writes
  machine code through a compiler such as LLVM can take longer to compile a query than to run it
  on a small input. Problem 19.3 is about that.
- **Whether every value fits in a register.** The count takes a value in a local variable to be
  written nowhere. A real compiler keeps it in a register only while there are registers free.
- **The branches.** The compiled loop has an `if` for every filter and every row, and each is
  predicted as in ch06. The interpreter's filters can select rows without branching on them.
  The panel does not count either.
- **What compiling to machine code would gain.** The generated loop runs under Python's
  interpreter, which is why the timing above puts it behind pyarrow's kernels. The counts
  describe what compiled machine code would do; the time describes this loop.

## What this means for your design

- **Know which your engine is.** An interpreting engine pays its overhead once a batch, whatever
  the query; a compiling one pays once a query, before the first row.
- **Many small queries favour interpreting.** A dashboard of short queries on small tables can
  spend more compiling than running. Compiling engines cache compiled code for this, and prepared
  statements help them reuse it (problem 19.2).
- **Long computations favour compiling.** A query that computes many values on every row writes
  an array for each in an interpreter, and none in a compiled loop.
- **Write an expression once, and check what the engine made of it.** DuckDB computed the unit
  price twice because the query asked for it twice. Its profile will not say so; the counts above
  took a function that counted.

## Key takeaways

:::{div}
:class: takeaways

- **Compiling moves the decisions before the first row.** The compiler visits each node once; the
  loop it writes decides nothing as it runs.
- **Values stay in variables.** A compiled loop writes only its result; an interpreter writes an
  array for every kernel and a batch for every filter.
- **A kernel fills the vector lanes; a loop fills one.** The compiled loop runs more instructions
  than the kernels do.
- **Compiling costs once a query, interpreting once a batch.** Which is cheaper depends on how
  many batches a query runs over.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: compiling_a_query
```

**19.1 Compile the totals.** Write `generate_totals`: the source of one loop that tests a
pipeline's filters on each row and adds a value to its key's total, ch07's aggregate compiled into
the pipeline. The graders compile your source, run it over the orders for several filters, keys
and values, and compare every total with DuckDB's `GROUP BY`; they check it is one loop, and calls
no kernel.

**19.2 One shape, many queries.** Write `parameterise`: a tree's shape, with each constant taken
out and numbered, and the constants. Queries that differ only in their constants then share a
shape, and one compiled function can serve them all. The graders take random trees apart and put
them back together, and check that two of the chapter's queries share a shape exactly when they
should.

**19.3 Diagnose the slow dashboard.** No test. A team moved its dashboard to an engine that
compiles every query. Each of its hundreds of queries reads a few rows of a small table, and the
dashboard is slower than before. Here is ch01's pipeline over more and more of the orders:

```{include} _generated/compile-or-interpret.md
```

Explain what the interpreter's visits and the compiler's add up to for each size, and why the
first rows show the dashboard's trouble. What would you ask the engine to do, and what would you
change about the queries? A good answer compares a cost paid once a query with one paid once a
batch, says where they cross, and uses problem 19.2's shapes to propose a cache.

## Where to go next

- **Compiling queries.** Thomas Neumann, *Efficiently Compiling Efficient Query Plans for Modern
  Hardware*, VLDB 2011: pipelines compiled into loops that keep values in registers, HyPer's
  design.
- **Compiled against vectorised.** Timo Kersten, Viktor Leis, Alfons Kemper, Thomas Neumann,
  Andrew Pavlo and Peter Boncz, *Everything You Always Wanted to Know About Compiled and
  Vectorized Queries But Were Afraid to Ask*, VLDB 2018: the two built side by side, and where
  each wins.
- **Vectors.** Peter Boncz, Marcin Zukowski and Niels Nes, *MonetDB/X100: Hyper-Pipelining Query
  Execution*, CIDR 2005: the vector-at-a-time interpreter DuckDB descends from.
- **Code generation in Spark.** Michael Armbrust and others, *Spark SQL: Relational Data
  Processing in Spark*, SIGMOD 2015: Catalyst, and the code it generates for expressions.
