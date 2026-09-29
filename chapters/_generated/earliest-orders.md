| Query | Bytes read |
|---|---:|
| `first_orders.sql` | 67,190 |
| `earliest_orders.sql` | 305,947 |

| Row group | Earliest `order_date` | Latest `order_date` |
|---:|---|---|
| 0 | 2024-01-01 | 2024-02-06 |
| 1 | 2024-02-06 | 2024-03-14 |
| 2 | 2024-03-14 | 2024-04-19 |
| 3 | 2024-04-19 | 2024-05-26 |
| 4 | 2024-05-26 | 2024-07-01 |
| 5 | 2024-07-02 | 2024-08-07 |
| 6 | 2024-08-07 | 2024-09-13 |
| 7 | 2024-09-13 | 2024-10-19 |
| 8 | 2024-10-19 | 2024-11-25 |
| 9 | 2024-11-25 | 2024-12-31 |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
