| Operator | Rows out, estimated | What it does |
|---|---:|---|
| TOP_N | none | Top: `10`; Order By: `"orders-shuffled".amount DESC, "orders-shuffled".order_id ASC` |
| PARQUET_SCAN | 20,000 | Projections: `order_id, customer_id, amount` |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-shuffled.parquet`, at build time.*
