| Operator | Rows out, estimated | What it does |
|---|---:|---|
| ORDER_BY | none | Order By: `sum(o.amount) DESC` |
| HASH_GROUP_BY | 10,000 | Groups: `#0`; Aggregates: `count_star(), sum(#1)` |
| PROJECTION | 20,000 | Projections: `country, amount` |
| PROJECTION | 20,000 | Projections: `__internal_compress_integral_usmallint(#0, 1), #1, __internal_compress_integral_usmallint(#2, 1), #3` |
| HASH_JOIN | 20,000 | Join Type: `INNER`; Conditions: `customer_id = customer_id`; Build Min: `1`; Build Max: `1000` |
| PARQUET_SCAN | 20,000 | Projections: `customer_id, amount` |
| PARQUET_SCAN | 1,000 | Projections: `customer_id, country` |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet` and `fixtures/customers.parquet`, at build time.*
