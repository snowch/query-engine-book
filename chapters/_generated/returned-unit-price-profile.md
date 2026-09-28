| Operator | Rows in | Rows out, estimated | Rows out, measured |
|---|---:|---:|---:|
| PROJECTION | 729 | 800 | 729 |
| FILTER | 1,183 | 800 | 729 |
| TABLE_SCAN | 20,000 | 4,000 | 1,183 |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
