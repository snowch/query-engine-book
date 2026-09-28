| Operator | Rows out, estimated | What it does |
|---|---:|---|
| PROJECTION | 800 | Projections: `order_id, customer_id, unit_price` |
| FILTER | 800 | Expression: `((amount / CAST(quantity AS DOUBLE)) > 100.0)` |
| PARQUET_SCAN | 4,000 | Projections: `amount, quantity, order_id, customer_id`; Filters: `status='returned' AND status IS NOT NULL` |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
