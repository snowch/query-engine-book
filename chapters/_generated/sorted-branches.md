| The amounts in the order of | Kernel | Rows kept | Branches | Mispredictions |
|---|---|---:|---:|---:|
| the file: by date | with a branch | 9,999 | 40,000 | 10,182 |
| the file: by date | without a branch | 9,999 | 20,000 | 2 |
| the amounts | with a branch | 9,999 | 40,000 | 4 |
| the amounts | without a branch | 9,999 | 20,000 | 2 |

The test is `amount > 529.58`.

*Computed by the book's engine and branch model on `fixtures/orders-sorted.parquet`, at build time.*
