| Column | Dictionary page, `orders-paged` | Dictionary page, the default copy |
|---|---:|---:|
| `order_id` | none | 80,084 |
| `order_date` | 1,486 | 1,486 |
| `customer_id` | 3,814 | 3,814 |
| `amount` | none | 92,235 |

| Scan by page | Rows decoded | Bytes read | Requests |
|---|---:|---:|---:|
| orders-paged | 1,024 | 18,683 | 14 |
| the default copy | 1,024 | 184,908 | 16 |

*Computed by the book's engine on `fixtures/orders-paged.parquet` and on a copy of it that pyarrow 18.1.0 writes, at build time, with its default dictionaries.*
