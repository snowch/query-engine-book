| Your engine's operator | Rows in | Rows out | DuckDB's operator | Rows in | Rows out |
|---|---:|---:|---|---:|---:|
| HashJoin `customer_id = customer_id: order_id, country` | 21,000 | 20,000 | HASH_JOIN | 21,000 | 20,000 |
| Scan `orders-sorted.parquet: order_id, customer_id` | 20,000 | 20,000 | TABLE_SCAN | 20,000 | 20,000 |
| Scan `customers.parquet: customer_id, country` | 1,000 | 1,000 | TABLE_SCAN | 1,000 | 1,000 |

*Computed by the book's engine and DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
