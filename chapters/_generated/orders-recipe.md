| Column | How it was generated |
|---|---|
| `order_id` | 1 to 20,000, in order |
| `status` | shipped 70%, delivered 20%, returned 6%, cancelled 3%, pending 1% |
| `quantity` | a whole number from 1 to 10, each equally likely |
| `amount` | `quantity` times a unit price drawn evenly between 2 and 250 |

*Computed by `fixtures/generate.py` on `fixtures/orders-sorted.parquet`, at build time.*
