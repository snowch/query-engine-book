---
title: "Part VI: Other ways to run a plan"
---

(part-other-ways-to-run-a-plan)=
# Part VI: Other ways to run a plan

> The plan is chosen: what changes when an engine runs it another way?

Every plan so far ran the same way: each operator pulled batches from the one below it, and the
top of the plan drove the run. The engines you use do not all run that way. This part takes one
plan and runs it differently, and counts what the difference changes. It starts by turning the
loop upside down, so that the scan pushes rows up the plan, and asks what that costs in stopping
early and saves in reading once for several consumers ([ch18](#pushing-instead-of-pulling)).
Last, it turns a pipeline into code before the first row is read, and counts what the
interpreter no longer does, and what the code gives up in return ([ch19](#compiling-a-query)).
