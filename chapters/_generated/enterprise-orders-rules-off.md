| DuckDB, with | Operators, top down | Rows from the scans | Bytes read |
|---|---|---:|---:|
| every rule on | PROJECTION, HASH_JOIN, FILTER, TABLE_SCAN, TABLE_SCAN | 20,229 | 301,746 |
| `filter_pushdown` off | PROJECTION, PROJECTION, HASH_JOIN, FILTER, TABLE_SCAN, FILTER, TABLE_SCAN | 20,997 | 308,099 |
| `unused_columns` off | PROJECTION, HASH_JOIN, FILTER, TABLE_SCAN, TABLE_SCAN | 20,229 | 301,746 |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet` and `fixtures/customers.parquet`, at build time.*
