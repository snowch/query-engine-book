---
title: Preface
---

(preface)=
# Preface

## What this book is

This book is for data engineers who run queries every day and want to know what a query costs.
You learn it by following a small query engine, one operator at a time, and the work it counts.
The examples help you predict how a design choice affects bytes read, rows moved, memory held
and data sent between machines. The optional implementation uses Python and Apache Arrow, a
format for holding columns in memory.

A query engine reads, moves and transforms data. A plan lists the steps the engine will run.
A profile records what those steps did during a run. The six parts use the work recorded in
profiles to answer different design questions.

- [Part I, Seeing a query](#part-seeing-a-query). Follow the rows through a plan.
- [Part II, Reading less](#part-reading-less). Find which data the engine can skip.
- [Part III, Computing](#part-computing). Compare the cost of grouping, joining and ordering rows.
- [Part IV, Planning](#part-planning). Follow the planner from SQL text to a plan.
- [Part V, Scaling out](#part-scaling-out). Count the cost of sharing work between workers.
- [Part VI, Other ways to run a plan](#part-other-ways-to-run-a-plan). Compare ways of running the same plan.

You can read the whole argument without reading code, installing software or running an example.
Plans, worked results and comparisons are already on the page, including when JavaScript is
disabled. The examples assume you already read and run SQL queries. The reading path introduces
the hardware and file formats it uses. [Running the lab](#running-the-lab) explains browser tools
and optional local setup. The companion Parquet and computer systems books offer more depth.

## Choose your route

| Route | What to read or open | What you get |
|---|---|---|
| Read | Explanations, worked results, Compare, limitations and design guidance | Understand what a query costs without code or execution |
| Explore | Optional prediction panels, query editors and live timings | Test how changing an input changes the work |
| Build | Optional Python listings and practice workbenches | Implement the engine and check your changes |

Start with the chapter’s learning goal. Try its understanding check before revealing the
explanation. You can skip **Building it** and continue at **Compare**; keep the limitations and
design sections, which explain what the evidence does and does not support.

## How a chapter works

Every chapter follows the same method: observe, build, compare, then design. It has the same
ten sections, so you always know where you are:

1. **The question** it answers, and why the previous chapter left it open.
2. **Observe**: the query run in DuckDB, the reference engine, with its plan and its profile.
3. **Predict, then measure**: make a prediction, then read the worked result; optionally rerun or change it.
4. **Building it**: optional implementation, with code quoted from the working tree.
5. **Compare**: your engine's results and counters beside DuckDB's.
6. **What this cannot tell you**: the limits of the experiment, the model and the code.
7. **What this means for your design**: the choices in your own systems that change.
8. **Key takeaways**.
9. **Problems**: optional kernels to write, graded by tests and simulators, and one slow query to
   diagnose. The understanding check needs no code.
10. **Where to go next**: papers, engine source code, and the companion books.

## Three rules the book keeps

**No number is typed into the prose.** A row count, a byte count or a request total appears in
a generated table, computed by an engine when the book was built. If the engine, DuckDB or a
fixture changes, the build recomputes the numbers and fails if a committed table is stale.

**No code is pasted into the prose.** Every block of Python and SQL is quoted from the working
tree, so the book cannot drift from the code it describes. The bar above each block names the
file.

**Counters first, then time.** An engine's work is counted in rows, batches, bytes and requests,
which are the same on every machine and in your browser, so the book reasons with them. Where a
design saves time, a chapter lets you time it, in your browser, when you press the button. Times
differ from run to run and machine to machine, so the page keeps none, and compares cases timed
together.

## Where this starts

Start with [The plan is the map](#the-plan-is-the-map). The page prepares three runs in DuckDB.
Predict where the rows will change, then check the worked plans. Later chapters ask for counts
after introducing the information needed to estimate them.
