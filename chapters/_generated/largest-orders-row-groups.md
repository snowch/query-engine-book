| Row group | Rows | Smallest `amount` | Largest `amount` | Read by the scan |
|---:|---:|---:|---:|---|
| 0 | 2,000 | 3.3 | 2482.37 | yes |
| 1 | 2,000 | 2.19 | 2485.14 | yes |
| 2 | 2,000 | 3.06 | 2496.85 | yes |
| 3 | 2,000 | 2.76 | 2496.75 | yes |
| 4 | 2,000 | 4.3 | 2494.48 | yes |
| 5 | 2,000 | 3.26 | 2492.95 | yes |
| 6 | 2,000 | 2.31 | 2485.78 | yes |
| 7 | 2,000 | 2.04 | 2487.82 | yes |
| 8 | 2,000 | 4.72 | 2469.75 | yes |
| 9 | 2,000 | 2.63 | 2490.45 | yes |

The scan read 10 of 10 row groups: it decoded 20,000 rows, handed up 93, and read 242,916 of the file's 497,857 bytes.

*Computed by the book's engine on `fixtures/orders-sorted.parquet`, at build time.*
