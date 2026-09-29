| Operator | Rows out, estimated | What it does |
|---|---:|---|
| PARQUET_SCAN | 4,000 | Projections: `order_id, customer_id, amount`; Filters: `order_date>='2024-03-01'::DATE AND order_date<'2024-03-15'::DATE AND order_date IS NOT NULL` |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-paged.parquet`, at build time.*
