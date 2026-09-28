| Your engine's operator | Rows in | Rows out | DuckDB's operator | Rows in | Rows out |
|---|---:|---:|---|---:|---:|
| Scan `orders-sorted.parquet: order_id, customer_id, amount; order_date >= 2024-03-01 AND order_date < 2024-03-15` | 4,000 | 765 | TABLE_SCAN | 20,000 | 765 |

*Computed by the book's engine and DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
