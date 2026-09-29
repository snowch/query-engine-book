---
title: "Part III: Computing"
---

(part-computing)=
# Part III: Computing

> Once the rows are in memory, what does each operator cost the processor?

Part II made the engine read less. What it does read, it must compute: every expression a query
writes is evaluated for every row that reaches it. This part counts what that costs the
processor, starting with how an engine evaluates an expression, and why engines work a batch of
rows at a time rather than one row ([ch06](#expressions-and-vectorised-kernels)). Then it groups
rows, and finds that what a group costs depends on how many there are, and on the cache
([ch07](#hash-aggregation)).
