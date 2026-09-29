| Operator | Rows out, estimated | What it does |
|---|---:|---|
| PROJECTION | 20,000 | Projections: `order_id, country` |
| HASH_JOIN | 20,000 | Join Type: `INNER`; Conditions: `customer_id = customer_id`; Build Min: `1`; Build Max: `1000` |
| PARQUET_SCAN | 20,000 | Projections: `customer_id, order_id` |
| PARQUET_SCAN | 1,000 | Projections: `customer_id, country` |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
