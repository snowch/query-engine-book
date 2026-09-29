| Operator | Rows out, estimated | What it does |
|---|---:|---|
| PROJECTION | 10,000 | Projections: `__internal_decompress_integral_integer(#0, 1), #1, #2` |
| PERFECT_HASH_GROUP_BY | none | Groups: `#0`; Aggregates: `count_star(), sum(#1)` |
| PROJECTION | 20,000 | Projections: `customer_id, amount` |
| PROJECTION | 20,000 | Projections: `__internal_compress_integral_usmallint(#0, 1), #1` |
| PARQUET_SCAN | 20,000 | Projections: `customer_id, amount` |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
