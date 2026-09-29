| Operator, top down | Rows out, one thread | Rows out, four threads |
|---|---:|---:|
| PROJECTION | 948 | 948 |
| PERFECT_HASH_GROUP_BY | 948 | 948 |
| PROJECTION | 20,000 | 20,000 |
| PROJECTION | 20,000 | 20,000 |
| TABLE_SCAN | 20,000 | 20,000 |

| File | Row groups |
|---|---:|
| `orders-sorted.parquet` | 10 |
| `orders-paged.parquet` | 1 |

*Computed by DuckDB 1.1.2 with one thread and with four on `fixtures/orders-sorted.parquet` and `fixtures/orders-paged.parquet`, at build time.*
