| Your engine's operator | Rows in | Rows out | DuckDB's operator | Rows in | Rows out |
|---|---:|---:|---|---:|---:|
| TopK `amount DESC, order_id ASC LIMIT 10` | 20,000 | 10 | TOP_N | 20,000 | 10 |
| Scan `orders-shuffled.parquet: order_id, customer_id, amount` | 20,000 | 20,000 | TABLE_SCAN | 20,000 | 20,000 |

*Computed by the book's engine and DuckDB 1.1.2 with one thread on `fixtures/orders-shuffled.parquet`, at build time.*
