| Operator | Rows out, estimated | What it does |
|---|---:|---|
| PROJECTION | 800 | Projections: `order_id, country, unit_price` |
| HASH_JOIN | 800 | Join Type: `INNER`; Conditions: `customer_id = customer_id`; Build Min: `1`; Build Max: `1000` |
| FILTER | 4,000 | Expression: `((amount / CAST(quantity AS DOUBLE)) > 100.0)` |
| PARQUET_SCAN | 20,000 | Projections: `customer_id, amount, quantity, order_id` |
| PARQUET_SCAN | 200 | Projections: `customer_id, country`; Filters: `segment='enterprise' AND segment IS NOT NULL` |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet` and `fixtures/customers.parquet`, at build time.*
