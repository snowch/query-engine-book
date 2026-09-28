| File | Rows | Row groups | Bytes | Why it exists |
|---|---:|---:|---:|---|
| `customers.parquet` | 1,000 | 1 | 18,117 | The dimension table orders.customer_id points into: one row per customer, small enough to be the build side of any join. |
| `orders-shuffled.parquet` | 20,000 | 10 | 534,245 | The same orders in a seeded random order. Every row group spans the whole year, so no filter on the date can skip one: the control for orders-sorted. |
| `orders-sorted.parquet` | 20,000 | 10 | 497,857 | Orders written in date order. Each row group holds a narrow run of dates, so a filter on the date can skip most row groups, and neighbouring rows are neighbours in memory. |

*Read from the manifests `fixtures/generate.py` wrote, at build time.*
