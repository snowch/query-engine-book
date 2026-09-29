| Fan-in | Runs written | Merge passes | Rows spilled | Bytes spilled | Bytes read back |
|---:|---:|---:|---:|---:|---:|
| 2 | 20 | 4 | 80,000 | 1,681,680 | 1,681,680 |
| 4 | 13 | 2 | 40,000 | 841,728 | 841,728 |
| 8 | 12 | 2 | 40,000 | 841,232 | 841,232 |
| 16 | 10 | 1 | 20,000 | 421,760 | 421,760 |

The rows take 400,000 bytes; the memory limit is 40,001.

*Computed by the book's engine on `fixtures/orders-shuffled.parquet`, at build time.*
