| Operator | Rows out, estimated | What it does |
|---|---:|---|
| PROJECTION | 3,333 | Projections: `order_id, name, country` |
| HASH_JOIN | 3,333 | Join Type: `INNER`; Conditions: `customer_id = customer_id`; Build Min: `1`; Build Max: `1000` |
| PARQUET_SCAN | 20,000 | Projections: `customer_id, order_id` |
| HASH_JOIN | 166 | Join Type: `INNER`; Conditions: `country = country` |
| PARQUET_SCAN | 1,000 | Projections: `customer_id, country, name` |
| PARQUET_SCAN | 2 | Projections: `country, name`; Filters: `region='Asia' AND region IS NOT NULL` |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, `fixtures/customers.parquet` and `fixtures/countries.parquet`, at build time.*
