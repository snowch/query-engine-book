| Column | Arrow type | Nulls | Validity bitmap | Offsets | Values or data |
|---|---|---:|---:|---:|---:|
| `file_row_number` | `int64` | 0 | 2,500 | none | 160,000 |
| `order_id` | `int64` | 0 | 2,500 | none | 160,000 |
| `order_date` | `date32[day]` | 0 | 2,500 | none | 80,000 |
| `status` | `string` | 0 | 2,500 | 80,004 | 150,507 |
| `amount` | `double` | 0 | 2,500 | none | 160,000 |
| `note` | `string` | 2,981 | 2,500 | 80,004 | 394,039 |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-shuffled.parquet`, at build time.*
