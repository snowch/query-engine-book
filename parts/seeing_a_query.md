---
title: "Part I: Seeing a query"
---

(part-seeing-a-query)=
# Part I: Seeing a query

> What does an engine do with a query, and how do you watch it work?

Before you can reason about what a query costs, you need to see its work. This part reads a
real engine's plan and profile ([ch01](#the-plan-is-the-map)), then looks at the data an engine
moves between its operators, as it sits in memory ([ch02](#batches-in-memory)).
