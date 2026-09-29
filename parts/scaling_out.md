---
title: "Part V: Scaling out"
---

(part-scaling-out)=
# Part V: Scaling out

> What changes when a query's work is shared among many workers, on one machine or many?

Everything so far ran on one thread. This part shares the work out, and counts what sharing costs.
The book's DuckDB has one thread, in the page and when the book is built, so this part simulates
the workers with counters, as ch02 simulated a cache. It starts with the cores of one machine:
what a query must be split into for them to share it, and what no number of them can share
([ch14](#parallelism-on-one-machine)). Across machines, rows that must meet must be sent, and the
bytes sent depend on how the plan moves them ([ch15](#partitioning-and-shuffle)). A few popular
keys can leave one machine with most of the work ([ch16](#skew)). Last, a whole plan runs as
stages, and where the rows between them are kept decides what a failed machine costs
([ch17](#stages-and-distributed-execution)).