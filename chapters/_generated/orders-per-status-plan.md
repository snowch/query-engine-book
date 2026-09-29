| Operator | Rows out, estimated | What it does |
|---|---:|---|
| HASH_GROUP_BY | 10,000 | Groups: `#0`; Aggregates: `count_star(), sum(#1)` |
| PROJECTION | 20,000 | Projections: `status, amount` |
| PARQUET_SCAN | 20,000 | Projections: `status, amount` |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
