| | Count |
|---|---:|
| Returned orders, whose unit price the filter tests | 1,183 |
| Orders the projection returns, with their unit price | 729 |
| Unit prices computed | 1,912 |
| Calls that computed them, each on a vector of rows | 20 |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, with the division replaced by a function that counts its calls, at build time.*
