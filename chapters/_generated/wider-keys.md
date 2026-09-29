| GROUP BY | Groups | Slots probed | Table bytes | Cache misses |
|---|---:|---:|---:|---:|
| `customer_id` | 948 | 25,371 | 32,768 | 911 |
| `customer_id, status` | 2,117 | 27,191 | 65,536 | 2,356 |
| `customer_id, order_date` | 12,560 | 72,189 | 524,288 | 14,651 |

*Computed by the book's engine and cache model (512 lines of 64 bytes) on `fixtures/orders-sorted.parquet`, at build time.*
