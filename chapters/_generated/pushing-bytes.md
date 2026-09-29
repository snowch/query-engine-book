| The query asks | File | Bytes read | Scans of the file | Scans of a kept result |
|---|---|---:|---:|---:|
| How many returned orders? | `returned_count.sql` | 16,134 | 1 | 0 |
| Is there a returned order? | `any_returned.sql` | 9,211 | 1 | 0 |
| Big returners, the returned orders read by each consumer | `big_returners.sql` | 326,262 | 2 | 0 |
| Big returners, the returned orders read once and kept | `big_returners_materialized.sql` | 183,266 | 1 | 2 |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
