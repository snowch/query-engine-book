| Your engine's operator | Rows in | Rows out | DuckDB's operator | Rows in | Rows out |
|---|---:|---:|---|---:|---:|
| Project `order_id, customer_id, unit_price` | 729 | 729 | PROJECTION | 729 | 729 |
| Filter `amount / quantity > 100` | 1,183 | 729 | FILTER | 1,183 | 729 |
| Filter `status = 'returned'` | 20,000 | 1,183 | TABLE_SCAN | 20,000 | 1,183 |
| Scan `orders-sorted.parquet: order_id, customer_id, status, amount, quantity` | 20,000 | 20,000 | none | | |

*Computed by the book's engine and DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
