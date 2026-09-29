| Scan | Files opened | Requests | Bytes read | Rows decoded | Rows handed up |
|---|---:|---:|---:|---:|---:|
| Yours, by the table's metadata | 1 | 8 | 33,857 | 1,694 | 765 |
| Yours, by the table's files | 12 | 41 | 41,938 | 1,694 | 765 |
| DuckDB's, by a glob of the files | 12 | not reported | 41,938 | not reported | 765 |
| DuckDB's, by the month in the directory's name | 2 | not reported | 26,824 | not reported | 765 |

*Computed by the book's engine and DuckDB 1.1.2 with one thread, its reads counted at the file system on `fixtures/orders-by-month/`, at build time.*
