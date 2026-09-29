| Stage | Tasks | Rows in | Bytes shuffled on |
|---|---:|---:|---:|
| 1. read and shuffle by customer | 16 | 21,000 | 302,056 |
| 2. join, aggregate in part | 16 | 21,000 | 73,856 |
| 3. finish the aggregate | 16 | 191 | 6,208 |
| 4. sort | 1 | 12 | 0 |

*Computed by the book's engine on sixteen simulated nodes on `fixtures/orders-sorted.parquet` and `fixtures/customers.parquet`, at build time.*
