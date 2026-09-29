| Plan | Operators, top down | Rows from the scans | Bytes read | Rows out |
|---|---|---:|---:|---:|
| Your plain plan | Project, Filter, HashJoin, Project, Scan, Project, Scan | 21,000 | 515,966 | 4,033 |
| DuckDB's plan | PROJECTION, HASH_JOIN, FILTER, TABLE_SCAN, TABLE_SCAN | 20,229 | 301,746 | 4,033 |

*Computed by the book's planner and engine, and DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet` and `fixtures/customers.parquet`, at build time.*
