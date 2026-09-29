| How it evaluates | Batches | Nodes visited | Instructions | Lanes used | Rows kept |
|---|---:|---:|---:|---:|---:|
| A row at a time | 20,000 | 328,467 | 149,343 | 25% | 9,781 |
| In batches of 16 rows | 1,250 | 25,000 | 38,730 | 96% | 9,781 |
| In batches of 256 rows | 79 | 1,580 | 37,425 | 100% | 9,781 |
| In batches of 2,048 rows | 10 | 200 | 37,350 | 100% | 9,781 |
| In batches of 20,000 rows | 1 | 20 | 37,338 | 100% | 9,781 |

*Computed by the book's engine and a vector unit of 4 lanes on `fixtures/orders-sorted.parquet`, at build time.*
