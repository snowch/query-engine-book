| Condition | Your planner's estimate | DuckDB's estimate | Rows it keeps |
|---|---:|---:|---:|
| `order_date < DATE '2024-04-01'` | 4,986 | 4,000 | 4,973 |
| `status = 'returned'` | 4,000 | 4,000 | 1,183 |
| `amount > 2000` | 3,983 | 4,000 | 640 |
| `quantity = 1 AND amount > 300` | 1,761 | 4,000 | 0 |
| `customer_id = 1` | 20 | 4,000 | 3,583 |

*Computed by the book's planner and DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
