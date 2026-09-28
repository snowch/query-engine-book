| Operator | Rows out, estimated | What it does |
|---|---:|---|
| PROJECTION | 4,000 | Projections: `order_id, customer_id, unit_price` |
| FILTER | 4,000 | Expression: `(((amount / CAST(quantity AS DOUBLE)) > 100.0) AND (lower(status) = 'returned'))` |
| PARQUET_SCAN | 20,000 | Projections: `status, amount, quantity, order_id, customer_id` |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
