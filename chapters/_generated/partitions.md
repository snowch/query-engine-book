| Node, `hash(customer_id) % 4` | Orders | Customers |
|---:|---:|---:|
| 0 | 7,387 | 251 |
| 1 | 3,363 | 243 |
| 2 | 5,829 | 272 |
| 3 | 3,421 | 234 |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet` and `fixtures/customers.parquet`, at build time.*
