| Query | 1.5MB | 2MB | 2.5MB |
|---|---|---|---|
| `orders_by_amount.sql`, with a temporary directory | out of memory | finishes | finishes |
| `orders_by_amount.sql`, with none | out of memory | out of memory | finishes |
| `top_orders.sql`, with none | out of memory | finishes | finishes |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-shuffled.parquet`, at build time.*
