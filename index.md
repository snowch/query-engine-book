---
title: Preface
---

(preface)=
# Preface

## What this book is

This book is for data engineers who run queries every day and want to know what a query costs.
You learn it by following a small query engine, one operator at a time, and the work it counts.
You can also build it in Python on Apache Arrow. By the end you can look at a design choice (a sort order, a
partitioning scheme, a join, a memory limit) and predict how it changes the bytes read, the
rows moved, the memory used and the data shuffled, in any engine.

**A query engine is a machine for moving and transforming data.** A plan says where the data will
go; a profile says how much of it went. Every way an engine gets faster reads less, moves less,
holds less, computes less or sends less between machines, and the book asks one question, six
ways, one part each:

- **[Part I, Seeing a query](#part-seeing-a-query):** what happened to the data?
- **[Part II, Reading less](#part-reading-less):** could the engine have read less of it?
- **[Part III, Computing](#part-computing):** once it is in memory, what does working on it cost?
- **[Part IV, Planning](#part-planning):** how does an engine decide what to do, before it has read
  a row?
- **[Part V, Scaling out](#part-scaling-out):** what changes when one machine is not enough?
- **[Part VI, Other ways to run a plan](#part-other-ways-to-run-a-plan):** once the plan is
  chosen, what changes when the engine runs it another way?

You can read the whole argument without reading code, installing software or running an example.
Plans, worked results and comparisons are already on the page, including when JavaScript is
disabled. Reading Python is useful only for the optional implementation route. Experiments run
in your browser; [Running the lab](#running-the-lab) also explains the optional local setup. The book is self-contained: each idea about hardware or file
formats is introduced where it is first needed, with a deliberately small model. Two companion
books go deeper and are optional: *Parquet, byte by byte*, whose Parquet reader this engine reads
its files with, and a book on computer systems.

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

[ch01](#the-plan-is-the-map) runs one query in DuckDB, reads its plan and its profile, and asks
you to predict what each operator will produce before you measure it.
