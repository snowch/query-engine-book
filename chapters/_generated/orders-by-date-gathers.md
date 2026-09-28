| Column | Bytes in its buffers | Bytes fetched, sorted file | Bytes fetched, shuffled file |
|---|---:|---:|---:|
| `order_id` | 160,000 | 160,000 | 1,050,816 |
| `order_date` | 80,000 | 80,000 | 788,096 |
| `status` | 230,511 | 230,592 | 2,379,584 |
| `amount` | 160,000 | 160,000 | 1,050,816 |
| `note` | 476,543 | 476,672 | 2,565,824 |

*Computed by the book's engine and its cache model (512 lines of 64 bytes) on `fixtures/orders-sorted.parquet` and `fixtures/orders-shuffled.parquet`, at build time.*
