| Your engine's operator | Rows in | Rows out | DuckDB's operator | Rows in | Rows out |
|---|---:|---:|---|---:|---:|
| HashAggregate `customer_id: count(*), sum(amount)` | 20,000 | 948 | PERFECT_HASH_GROUP_BY | 20,000 | 948 |
| Scan `orders-sorted.parquet: customer_id, amount` | 20,000 | 20,000 | TABLE_SCAN | 20,000 | 20,000 |

*Computed by the book's engine and DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
