| Table | Groups | Lookups | Slots probed | Resizes | Table bytes | Cache misses |
|---|---:|---:|---:|---:|---:|---:|
| A hash table | 948 | 20,000 | 25,371 | 7 | 32,768 | 911 |
| A perfect hash table | 948 | 20,000 | 20,000 | 0 | 16,000 | 250 |

*Computed by the book's engine and cache model (512 lines of 64 bytes) on `fixtures/orders-sorted.parquet`, at build time.*
