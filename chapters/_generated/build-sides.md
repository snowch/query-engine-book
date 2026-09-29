| Query | DuckDB builds on | Your engine builds on | Build rows held | Held bytes | Cache misses |
|---|---|---|---:|---:|---:|
| `orders_with_country.sql` | `customers` | `customers` | 1,000 | 48,768 | 2,404 |
| `customers_with_orders.sql` | `customers` | `orders-sorted` | 20,000 | 352,768 | 19,689 |

*Computed by the book's engine and cache model, and DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet` and `fixtures/customers.parquet`, at build time.*
