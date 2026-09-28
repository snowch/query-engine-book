---
title: Projection and filter pushdown
---

(projection-and-filter-pushdown)=
# Projection and filter pushdown

:::{div}
:class: unwritten-note

This chapter is planned and not yet written. The outline below is the plan: the question it
answers and the piece of the engine it adds.
:::

## The question

How much of a file can a scan avoid reading, once it knows the columns and the predicate?

[To write: the paragraph that says why the previous chapter leaves this open.]

## Observe

[To write: the query run in DuckDB, its plan and its JSON profile read together.]

## Predict, then measure

[To write: a prediction the reader commits to, then the experiment that tests it.]

## Building it

[To write: Projection and filters pushed into the Parquet book's scan, counting the bytes read and the row groups skipped.]

## Compare

[To write: the engine's results and counters beside DuckDB's.]

## What this cannot tell you

[To write: what the experiment, the model and the code leave out.]

## What this means for your design

[To write: the choices in the reader's own systems that this changes.]

## Key takeaways

[To write: the claims made and shown above, each in bold with its reason.]

## Problems

[To write: problems as stubs in `exercises/projection_and_filter_pushdown.py`, graded by `exercises/tests/test_projection_and_filter_pushdown.py`, and one diagnose-the-slow-query problem.]

## Where to go next

[To write: papers, engine source code, and the optional depth in the companion books.]
