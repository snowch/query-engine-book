---
title: Batches in memory
---

(batches-in-memory)=
# Batches in memory

:::{div}
:class: unwritten-note

This chapter is planned and not yet written. The outline below is the plan: the question it
answers and the piece of the engine it adds.
:::

## The question

What does a batch of rows look like in memory, and why does the order you touch it in matter?

[To write: the paragraph that says why the previous chapter leaves this open.]

## Observe

[To write: the query run in DuckDB, its plan and its JSON profile read together.]

## Predict, then measure

[To write: a prediction the reader commits to, then the experiment that tests it.]

## Building it

[To write: Arrow arrays built from raw buffers, a validity bitmap decoded by hand, and sorted and shuffled gathers run through a cache simulator.]

## Compare

[To write: the engine's results and counters beside DuckDB's.]

## What this cannot tell you

[To write: what the experiment, the model and the code leave out.]

## What this means for your design

[To write: the choices in the reader's own systems that this changes.]

## Key takeaways

[To write: the claims made and shown above, each in bold with its reason.]

## Problems

[To write: problems as stubs in `exercises/batches_in_memory.py`, graded by `exercises/tests/test_batches_in_memory.py`, and one diagnose-the-slow-query problem.]

## Where to go next

[To write: papers, engine source code, and the optional depth in the companion books.]
