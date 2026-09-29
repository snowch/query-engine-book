---
title: From SQL to a logical plan
---

(from-sql-to-a-logical-plan)=
# From SQL to a logical plan

## The question

How does an engine turn the text of a query into a plan it can run, and what does the plainest
plan cost?

Every plan so far was written by hand. [ch01](#the-plan-is-the-map) read DuckDB's plan and built
the same operators; each chapter since has added an operator and wired it in by hand, choosing
the columns each scan reads and the conditions it tests. An engine does that for every query it
is given, from nothing but the text. This chapter writes the first half of that work: reading
the text, checking every name in it, and building the plan the text describes, in the plainest
way. Then it measures what the plainest way costs.

## Observe

The query asks for the pricier orders of enterprise customers, with each customer's country:

```{literalinclude} ../queries/enterprise_orders.sql
:language: sql
```

DuckDB can show the plan it built from the text, before it changed anything:

```{include} _generated/enterprise-orders-logical.md
```

And the plan it runs:

```{include} _generated/enterprise-orders-plan.md
```

1. **The first plan follows the text.** A projection for the `SELECT` list, a filter for the
   `WHERE`, a join for the `JOIN`, and a scan for each table, in the order SQL says a query
   means: join the tables, keep the rows, compute the columns.
2. **Its scans test nothing.** Both conditions wait in the filter above the join, which sees every
   pair of order and customer.
3. **Every name is resolved and every type is explicit.** `segment` and `amount` lost their
   tables' names, because DuckDB has already worked out which table each came from. DuckDB also
   wrote down each type it must convert: `quantity` becomes a `DOUBLE` for the division, and the
   `100` too, to be compared with a `DOUBLE`.
4. **The plan it runs is another plan.** The segment is tested inside the customers' scan, the
   price in a filter on the orders alone, below the join, and each scan reads only the columns it
   needs. The rows out are the same; the work is not.

The first plan says what the query means, and nothing about how to run it: it is a **logical
plan**, a tree of steps such as *join*, *filter* and *read a table*, each saying what it hands
up. The plan an engine runs is its physical plan, from [ch01](#the-plan-is-the-map). Between
the two, DuckDB rewrote the logical plan, and rewriting is the next chapter's subject. This
chapter builds the logical plan and runs it as it stands.

## Predict, then measure

Your planner builds the plain plan. Each table becomes a scan of every column, the conditions
become one filter above the scans and the join, and the `SELECT` list becomes a projection at the
top.

Predict the bytes the plain plan reads for three queries: ch01's returned orders, ch03's
fortnight in March, and this chapter's enterprise orders. Beside each, the panel shows what the
plan written by hand for that query read.

```lab
experiment: measure
of: planning
```

The panel draws what your engine counted when the book was built. Its button runs the same plans
again in your browser.

- **The plain plan reads the whole file, whatever the query asks.** Every column of every row
  group, for the returned orders and for the fortnight alike: the query's text changes nothing
  the scan does.
- **The plans written by hand read less, in the ways Part II built.** They read only the columns
  they use, test conditions inside the scan, and skip the row groups the file's statistics rule
  out.
- **The chart widens the fortnight.** The plain plan reads the same bytes for a day and for most
  of the year. The hand-written plan reads a row group more each time the window reaches one, and
  still reads only three columns.
- **Every plain plan gives the right rows.** A plan's cost and its answer are separate things.
  The planner's first duty is the answer, and everything after this chapter is about cost.

## Building it

### Tokens

The text arrives as characters. The parser's first step cuts it into **tokens**: the words,
numbers, strings and operators the grammar is made of, with the spaces and comments dropped. One
regular expression names each kind:

```{literalinclude} ../python/query_lab/sql.py
:language: python
:start-at: TOKEN = re.compile(
:end-before: def tokenize(
```

A word is a keyword, such as `SELECT`, or a name, such as `amount`: the keywords are listed, and
anything else is a name.
A string keeps its quotes until the parser reads it, so `'returned'` is never mistaken for a
column.

### Recursive descent

The parser reads the tokens by **recursive descent**: a method for each kind of phrase in the
grammar, each calling the methods for the phrases inside it. A query is a `SELECT` list, a table,
and optional clauses; a condition is an expression. The expressions carry SQL's precedence, one
method for each level, loosest first. Each method reads its operands by calling the next,
tighter one, so a tighter operator is grouped first:

```{literalinclude} ../python/query_lab/sql.py
:language: python
:start-at: def disjunction(self)
:end-before: def unary(self)
```

```run
tests: test_planner.py
select: precedence
```

Swap `"or"` and `"and"` between `disjunction` and `conjunction`, in the test and in the call,
so that `AND` is the looser, and run the engine's tests on your edit: `a = 1 OR b = 1 AND c = 1` now reads as `(a = 1 OR b = 1) AND c = 1`, and the
precedence tests say so.

What comes out is the query's **syntax tree**: the text's parts, as the text wrote them, in
ch06's expression trees and a `Query` that holds the rest. It says which tables and which
conditions, and nothing about whether they make sense.

### Binding

**Binding** checks that they do. The planner reads each table's schema from its file's footer,
and resolves every column the query names to the table it belongs to. A name no table has is an
error; so is a name two tables share, unless the query says which:

```{literalinclude} ../python/query_lab/planner.py
:language: python
:start-at: def resolve(self, name: str)
:end-before: def bind(self, expr
```

In a join, the planner names each column for its table, `o.customer_id` and `c.customer_id`, so
the two stay apart all the way up the plan.

### The plain plan

The planner then builds the logical plan in the order SQL defines a query's meaning. Read every
table, whole. Join them as the text joins them. Keep the rows the `WHERE` holds for. Group, if
the query groups. Compute the `SELECT` list. Sort, then limit:

```{literalinclude} ../python/query_lab/planner.py
:language: python
:start-at: def logical_plan(
:end-before: def _grouped(
```

Your planner's logical plan for the chapter's query, beside DuckDB's first plan:

```{include} _generated/enterprise-orders-plain.md
```

The same steps, in the same order. The two scans read every column their files hold.

### Operators for the steps

Each step of the logical plan becomes one of the operators the earlier chapters built. A read
becomes a scan, and in a join a projection that renames its columns for its table; a filter
evaluates ch06's expression tree on each batch; a join becomes ch08's hash join, built on the
table the text names second:

```{literalinclude} ../python/query_lab/planner.py
:language: python
:start-at: def physical_plan(
:end-before: def plan(
```

A `LIMIT` has no operator of its own: that is problem 3.3's, which you may have written. The
planner runs it as ch09's top-k with nothing to order by, which keeps the first rows it is given.
It reads every row its child hands up to do so, where problem 3.3's limit stops asking.

The book's tests plan every query in `queries/` that reads one plain file, and require DuckDB's
rows for each. The three that read many files, or pass `read_parquet` options, are refused with a
message that says why, and so are the few in later chapters that ask one question inside another,
which this parser does not read.

## Compare

Your plain plan beside DuckDB's, run:

```{include} _generated/enterprise-orders-compare.md
```

- **Both hand up the same rows.** The plain plan is a correct plan.
- **DuckDB read fewer bytes and handed fewer rows out of its scans.** Its binder asks each scan
  for only the columns the query names, four of the orders' seven, where your plain planner asks
  for all of them. And a rewrite moved the segment into the customers' scan, which kept only the
  enterprise customers.
- **DuckDB's orders' scan handed up a few orders fewer than there are.** The join's build side
  told the scan, as it ran, the smallest and largest customer id it held: ch08's `Build Min` and
  `Build Max`. The few orders of customers outside that range never left the scan.
- **DuckDB has no renaming projections.** Its binder refers to a column by the number of its
  table and its place in that table, not by a name, so two tables' `customer_id` never collide.
  Your planner renames them, and pays a projection for each table in a join.

## What this cannot tell you

- **How much SQL DuckDB reads.** Its parser is derived from PostgreSQL's, and reads subqueries,
  window functions, common table expressions and much more. Your parser reads the book's
  queries and little else.
- **What planning costs.** The counters count what a plan does, not the work of making it. For
  these queries it is small. For a query that joins many tables, choosing a plan can cost more
  than running it.
- **How DuckDB types an expression.** DuckDB's binder decides each expression's type before
  anything runs, and writes a cast wherever types differ. Your planner leaves types to Arrow's
  kernels, which decide as each batch arrives.
- **How a real parser reports mistakes.** Yours stops at the first token it did not expect.
  Production parsers recover and report several errors at once, with a caret under each.

## What this means for your design

- **Read both of DuckDB's plans.** `PRAGMA explain_output = 'all'` before `EXPLAIN` shows the
  plan as bound and the plan as rewritten. What moved between them is the rewriting's work, and
  what did not move is what it could not do.
- **Qualify every column in a join.** An unqualified name that one table has today is an error
  the day another table gains a column of the same name.
- **`SELECT *` asks for every column.** In a plan with no rewriting, every column is read, held
  and handed up. A planner may prune the ones nothing uses, but only if it can see that nothing
  does.
- **Write the query for its meaning, then read the plan.** The text says what you want. How it
  runs is the planner's choice, and the only way to know what it chose is to look.

## Key takeaways

:::{div}
:class: takeaways

- **A parser turns text into a syntax tree.** Tokens first, then recursive descent, with one
  method for each level of precedence.
- **Binding makes the names mean something.** Every column is resolved to its table, or the query
  is refused.
- **The logical plan is the query's meaning as steps.** Built the plain way, it reads everything
  and filters late.
- **The plain plan is right, and expensive.** It gives DuckDB's rows and reads the whole of every
  file, whatever the query asks.
:::

## Problems

There are three problems. The first two are code with tests; the third is a slow query to
diagnose, with no test. Write your answers to the first two in the workbench, and run the graders
there. Your answers stay in this browser, and **Reset to the stubs** starts again.

```problems
chapter: from_sql_to_a_logical_plan
```

**11.1 Two more comparisons.** Teach the parser `BETWEEN` and `IN`, with or without `NOT`, by
writing its `comparison` method. Return a tree of the comparisons the engine already evaluates,
so that nothing after the parser changes. The graders parse a range of conditions with your
parser, run them through the book's planner, and compare the rows with DuckDB's. They also check
that `x BETWEEN a AND b AND c` leaves the last `AND` to the condition around it.

**11.2 Numbers for names.** Write `resolve_ordinals`: bind `GROUP BY 1` and `ORDER BY 2 DESC`,
which name items of the `SELECT` list by their place in it, to what they name. The graders plan
queries that group and sort by position, and compare the rows with DuckDB's.

**11.3 Diagnose the slow engine.** No test. A colleague's engine plans every query the plain way,
and every answer it gives is right. Its dashboard runs five of the book's queries, which you have
also seen planned by hand:

```{include} _generated/plain-or-written.md
```

For each query, which step of the plain plan does work the hand-written plan does not? What
rewrite of the logical plan would remove it? Which of those rewrites need only the query's text,
and which need to know something about the data? A good answer finds the columns, the conditions
and the sort, and notices which choices only statistics can make.

## Where to go next

- **Parsing.** Robert Nystrom, [*Crafting Interpreters*](https://craftinginterpreters.com/),
  chapters 4 to 6: tokens, syntax trees and recursive descent, precedence level by level.
- **The logical and the physical.** Goetz Graefe, *Query Evaluation Techniques for Large
  Databases*, ACM Computing Surveys, 1993: the separation this chapter keeps, and the operators on
  both sides of it.
- **A query engine from the ground up.** Andy Grove, *How Query Engines Work*, which builds a
  logical plan through a DataFrame interface before its SQL parser.
- **DuckDB's binder.** DuckDB's [source](https://github.com/duckdb/duckdb), in
  `src/planner/binder/`, which turns the parser's tree into the logical plan you observed.
