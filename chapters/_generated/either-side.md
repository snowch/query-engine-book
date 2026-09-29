| Plan | Operators, top down | Rows from the scans | Rows out of the join | Bytes read | Rows out |
|---|---|---:|---:|---:|---:|
| Your rules' plan | Project, Filter, HashJoin, Project, Scan, Project, Scan | 21,000 | 20,000 | 290,606 | 7,069 |
| DuckDB's plan | PROJECTION, PROJECTION, PROJECTION, FILTER, HASH_JOIN, TABLE_SCAN, TABLE_SCAN | 21,000 | 20,000 | 296,959 | 7,069 |

*Computed by the book's planner and rules, and DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet` and `fixtures/customers.parquet`, at build time.*
