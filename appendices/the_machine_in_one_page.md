---
title: The machine in one page
---

(the-machine-in-one-page)=
# The machine in one page

A query's cost is paid to a machine: to its processor, its memory, its storage and its network.
The book never times the machine. It counts on a model of it, the same on every computer and in
the page, and each chapter that builds a part of the model says what that part leaves out. This
page gathers them.

## From near to far

Data travels to the processor through a chain of stores, each larger and slower than the one
before it:

- **Registers** hold the values an instruction works on. A compiled loop keeps its values here
  ([ch19](#compiling-a-query)).
- **The cache** holds the lines of memory used recently. A read the cache holds is a hit; any
  other is a miss, and waits for memory ([ch02](#batches-in-memory)). Hash tables and joins live or
  die by it ([ch07](#hash-aggregation), [ch08](#joins)).
- **Memory** holds what the engine is working on. An operator that must hold more than memory
  allows writes some of it out and reads it back ([ch10](#memory-limits-and-spilling)).
- **Storage** holds the files. Object storage answers each request after a delay, however few
  bytes it asks for, so requests matter as much as bytes ([ch03](#projection-and-filter-pushdown),
  [ch05](#where-work-happens)).
- **The network** joins machines. Rows that must meet on one machine must cross it
  ([ch15](#partitioning-and-shuffle)).

The processor itself guesses which way each branch goes, and pays when it guesses wrong, and
applies one instruction to several values at once when the code lets it
([ch06](#expressions-and-vectorised-kernels)). Several cores share the machine, and the work of a
query must be cut into pieces for them to share it ([ch14](#parallelism-on-one-machine)).

## The book's model

```{include} ../chapters/_generated/machine.md
```

## What the model leaves out

- **Time.** Every model counts events: misses, mispredictions, instructions, requests, bytes. How
  long each takes differs from one machine to the next by more than the book's comparisons do, so
  a count says which design does less, and a time on your own machine says how much that is worth.
- **Levels and prediction.** A real processor has several levels of cache, fetches lines before
  they are asked for, and runs instructions out of order while it waits. The models have one
  level, fetch nothing early, and run in order.
- **Sharing.** Real cores share memory bandwidth and caches, and real machines share a network.
  The simulated workers and nodes never wait on each other, except where a chapter counts it.
- **Failure and variation.** Real storage is sometimes slow and real machines sometimes fail. The
  models never are, except where [ch17](#stages-and-distributed-execution) makes one fail on
  purpose.
