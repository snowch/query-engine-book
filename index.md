---
title: Preface
---

(preface)=
# Preface

## What this book is

This book is for data engineers who run queries every day and want to know what a query costs.
You learn it by building the thing that pays for it: a small query engine, one operator at a
time, in Python on Apache Arrow. By the end you can look at a design choice (a sort order, a
partitioning scheme, a join, a memory limit) and predict how it changes the bytes read, the
rows moved, the memory used and the data shuffled, in any engine.

You need a browser and nothing else: everything the book asks you to run, runs in the page. You
should be able to read Python. The book is self-contained: each idea about hardware or file
formats is introduced where it is first needed, with a deliberately small model. Two companion
books go deeper and are optional: *Parquet, byte by byte*, whose Parquet reader is this engine's
scan, and a book on computer systems.

## How a chapter works

Every chapter follows the same method: observe, build, compare, then design. It has the same
ten sections, so you always know where you are:

1. **The question** it answers, and why the previous chapter left it open.
2. **Observe**: the query run in DuckDB, the reference engine, with its plan and its profile.
3. **Predict, then measure**: you commit to a prediction, then run the experiment that tests it.
4. **Building it**: the operator's code, quoted from the working tree.
5. **Compare**: your engine's results and counters beside DuckDB's.
6. **What this cannot tell you**: the limits of the experiment, the model and the code.
7. **What this means for your design**: the choices in your own systems that change.
8. **Key takeaways**.
9. **Problems**: kernels for you to write, graded by tests and simulators, and one slow query to
   diagnose.
10. **Where to go next**: papers, engine source code, and the companion books.

## Three rules the book keeps

**No number is typed into the prose.** A row count, a byte count or a request total appears in
a generated table, computed by an engine when the book was built. If the engine, DuckDB or a
fixture changes, the build recomputes the numbers and fails if a committed table is stale.

**No code is pasted into the prose.** Every block of Python and SQL is quoted from the working
tree, so the book cannot drift from the code it describes. The bar above each block names the
file.

**Counters, not time.** An engine's work is counted in rows, batches, bytes and requests, which
are the same on every machine and in your browser. Times differ from run to run, so the book
never prints one.

## Where this starts

[ch01](#the-plan-is-the-map) runs one query in DuckDB, reads its plan and its profile, and asks
you to predict what each operator will produce before you measure it.
