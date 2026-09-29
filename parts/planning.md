---
title: "Part IV: Planning"
---

(part-planning)=
# Part IV: Planning

> How does an engine decide what to run for a query, from its text alone?

Every plan in Parts I to III was written by hand, from DuckDB's `EXPLAIN`. An engine has only the
query's text. This part writes the planner that turns the text into a plan: it reads the text,
checks every name in it, and builds the plan the text describes in the plainest way, then
measures what the plainest way costs ([ch11](#from-sql-to-a-logical-plan)).
