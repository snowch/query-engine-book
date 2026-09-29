---
title: "Part II: Reading less"
---

(part-reading-less)=
# Part II: Reading less

> How does an engine avoid reading most of its input?

The cheapest byte is the one an engine never reads. This part hands the columns and predicates
a query needs to the scan, and counts what that saves
([ch03](#projection-and-filter-pushdown)), then asks how finely a scan can skip, and what the
file must record for it to ([ch04](#statistics-and-pruning)).
