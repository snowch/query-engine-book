| Scan | Rows decoded | Rows handed up | Bytes read | Requests |
|---|---:|---:|---:|---:|
| Yours, by row group | 20,000 | 765 | 214,796 | 7 |
| Yours, by page | 1,024 | 765 | 18,683 | 14 |
| DuckDB's | not reported | 765 | 214,796 | not reported |

*Computed by the book's engine and DuckDB 1.1.2 with one thread, its reads counted at the file system on `fixtures/orders-paged.parquet`, at build time.*
