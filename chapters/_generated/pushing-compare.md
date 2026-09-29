| Query | Your engine | Your bytes read | DuckDB's bytes read |
|---|---|---:|---:|
| Is there a returned order? | a sink that wants one row | 8,344 | 9,211 |
| Big returners, one scan | a tee to both aggregates | 183,266 | 183,266 |
| Big returners, a scan each | each aggregate pulls its own scan | 366,532 | 326,262 |

*Computed by the book's engine and DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
