| Operator | Rows in | Rows out | Batches out | Bytes read | Requests | Peak memory, bytes |
|---|---:|---:|---:|---:|---:|---:|
| Project `order_id, customer_id, unit_price` | 729 | 729 | 10 | 0 | 0 | 1,780 |
| Filter `amount / quantity > 100` | 1,183 | 729 | 10 | 0 | 0 | 3,220 |
| Filter `status = 'returned'` | 20,000 | 1,183 | 10 | 0 | 0 | 4,809 |
| Scan `orders-sorted.parquet: order_id, customer_id, status, amount, quantity` | 20,000 | 20,000 | 10 | 302,983 | 53 | 71,124 |

*Computed by the book's engine on `fixtures/orders-sorted.parquet`, at build time.*
