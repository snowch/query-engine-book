| Scan | File | Row groups read | Rows decoded | Rows handed up | Bytes read | Requests |
|---|---|---:|---:|---:|---:|---:|
| Nothing pushed | `orders-sorted.parquet` | 10 | 20,000 | 20,000 | 497,853 | 73 |
| Nothing pushed | `orders-shuffled.parquet` | 10 | 20,000 | 20,000 | 534,241 | 73 |
| The columns pushed | `orders-sorted.parquet` | 10 | 20,000 | 20,000 | 286,150 | 43 |
| The columns pushed | `orders-shuffled.parquet` | 10 | 20,000 | 20,000 | 322,476 | 43 |
| The columns and the dates pushed | `orders-sorted.parquet` | 2 | 4,000 | 765 | 63,218 | 11 |
| The columns and the dates pushed | `orders-shuffled.parquet` | 10 | 20,000 | 765 | 322,476 | 43 |
| DuckDB's | `orders-sorted.parquet` | not reported | not reported | 765 | 63,218 | not reported |
| DuckDB's | `orders-shuffled.parquet` | not reported | not reported | 765 | 322,476 | not reported |

*Computed by the book's engine, and DuckDB 1.1.2 with one thread, its reads counted at the file system, on `fixtures/orders-sorted.parquet` and `fixtures/orders-shuffled.parquet`, at build time.*
