| File | Where the rows are tested | Bytes over the network | Requests | Bytes the storage read |
|---|---|---:|---:|---:|
| `orders-sorted.parquet` | In your engine | 63,218 | 11 | 63,218 |
| `orders-sorted.parquet` | In the storage | 16,040 | 1 | 63,218 |
| `orders-shuffled.parquet` | In your engine | 322,476 | 43 | 322,476 |
| `orders-shuffled.parquet` | In the storage | 17,984 | 1 | 322,476 |

*Computed by the book's engine and its storage that tests rows, on `fixtures/orders-sorted.parquet` and `fixtures/orders-shuffled.parquet`, at build time.*
