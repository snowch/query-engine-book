| Query | DuckDB's operator | Your engine's operator | Rows held | Comparisons | Rows handed up |
|---|---|---|---:|---:|---:|
| `orders_by_amount.sql` | `ORDER_BY` | `Sort` | 20,000 | 259,640 | 20,000 |
| `top_orders.sql` | `TOP_N` | `TopK` | 10 | 20,315 | 10 |

*Computed by the book's engine and DuckDB 1.1.2 with one thread on `fixtures/orders-shuffled.parquet`, at build time.*
