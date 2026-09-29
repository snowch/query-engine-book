| Operator | Rows out, estimated | What it does |
|---|---:|---|
| PROJECTION | 20,000 | Projections: `__internal_decompress_integral_bigint(#0, 1), __internal_decompress_integral_integer(#1, 1), #2` |
| ORDER_BY | none | Order By: `"orders-shuffled".amount DESC, "orders-shuffled".order_id ASC` |
| PROJECTION | 20,000 | Projections: `__internal_compress_integral_usmallint(#0, 1), __internal_compress_integral_usmallint(#1, 1), #2` |
| PARQUET_SCAN | 20,000 | Projections: `order_id, customer_id, amount` |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-shuffled.parquet`, at build time.*
