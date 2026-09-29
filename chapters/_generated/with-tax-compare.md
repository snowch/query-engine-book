| Your engine's operator | Rows in | Rows out | DuckDB's operator | Rows in | Rows out |
|---|---:|---:|---|---:|---:|
| Project `order_id, with_tax` | 9,781 | 9,781 | PROJECTION | 9,781 | 9,781 |
| Filter `(((amount / quantity) > (50 * 2)) and ((quantity + 1) > 3))` | 20,000 | 9,781 | FILTER | 16,021 | 9,781 |
| Scan `orders-sorted.parquet: order_id, amount, quantity` | 20,000 | 20,000 | none | | |

*Computed by the book's engine and DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
