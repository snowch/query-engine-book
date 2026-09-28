| Operator | Rows out, estimated | What it does |
|---|---:|---|
| PROJECTION | 20,000 | Projections: `__internal_decompress_integral_bigint(#0, 0), __internal_decompress_integral_bigint(#1, 1), #2, #3, #4, #5` |
| ORDER_BY | none | Order By: `read_parquet.order_date ASC, read_parquet.order_id ASC` |
| PROJECTION | 20,000 | Projections: `__internal_compress_integral_usmallint(#0, 0), __internal_compress_integral_usmallint(#1, 1), #2, #3, #4, #5` |
| READ_PARQUET | 20,000 | Projections: `file_row_number, order_id, order_date, status, amount, note` |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-shuffled.parquet`, at build time.*
