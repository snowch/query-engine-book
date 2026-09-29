| File | Row groups | Pages of `order_date` | DuckDB's bytes read, the fortnight | DuckDB's bytes read, every row |
|---|---:|---:|---:|---:|
| `orders-sorted.parquet` | 10 | no page index | 63,218 | 305,947 |
| `orders-paged.parquet` | 1 | 20 | 214,796 | 214,796 |

*Computed by DuckDB 1.1.2 with one thread, its reads counted at the file system, on `fixtures/orders-sorted.parquet` and `fixtures/orders-paged.parquet`, at build time.*
