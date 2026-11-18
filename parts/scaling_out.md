---
title: "Part V: Scaling out"
---

(part-scaling-out)=
# Part V: Scaling out

> What changes when a query's work is shared among many workers, on one machine or many?

The browser and build run DuckDB on one thread. This part uses a model to count what happens when
a query shares work across workers. Those counts describe the model's work, including bytes sent and
tasks repeated after failure. It starts with the cores of one machine:
what a query must be split into for them to share it, and what no number of them can share
([ch14](#parallelism-on-one-machine)). Across machines, rows that must meet must be sent, and the
bytes sent depend on how the plan moves them ([ch15](#partitioning-and-shuffle)). A few popular
keys can leave one machine with most of the work ([ch16](#skew)). Last, a whole plan runs as
stages, and where the rows between them are kept decides what a failed machine costs
([ch17](#stages-and-distributed-execution)).