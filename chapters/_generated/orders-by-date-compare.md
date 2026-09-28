| Column | Buffer | Your engine, bytes | DuckDB, bytes |
|---|---|---:|---:|
| `file_row_number` | validity | none | 2,500 |
| `file_row_number` | values | 160,000 | 160,000 |
| `order_id` | validity | none | 2,500 |
| `order_id` | values | 160,000 | 160,000 |
| `order_date` | validity | none | 2,500 |
| `order_date` | values | 80,000 | 80,000 |
| `status` | validity | none | 2,500 |
| `status` | offsets | 80,004 | 80,004 |
| `status` | data | 150,507 | 150,507 |
| `amount` | validity | none | 2,500 |
| `amount` | values | 160,000 | 160,000 |
| `note` | validity | 2,500 | 2,500 |
| `note` | offsets | 80,004 | 80,004 |
| `note` | data | 394,039 | 394,039 |

*Computed by the book's engine and DuckDB 1.1.2 with one thread on `fixtures/orders-shuffled.parquet`, at build time.*
