| Operator | Rows in | Rows out, estimated | Rows out, measured |
|---|---:|---:|---:|
| PROJECTION | 729 | 4,000 | 729 |
| FILTER | 20,000 | 4,000 | 729 |
| TABLE_SCAN | 20,000 | 20,000 | 20,000 |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
