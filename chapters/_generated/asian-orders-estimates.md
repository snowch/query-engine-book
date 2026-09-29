| Join, top down | Your estimate | Your rows | DuckDB's estimate | DuckDB's rows |
|---|---:|---:|---:|---:|
| `o.customer_id = c.customer_id` | 4,000 | 4,124 | 3,333 | 4,124 |
| `c.country = n.country` | 200 | 189 | 166 | 189 |

*Computed by the book's planner and DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, `fixtures/customers.parquet` and `fixtures/countries.parquet`, at build time.*
