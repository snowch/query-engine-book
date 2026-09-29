| Query | Groups | Bytes shuffled, every order | Bytes shuffled, two phases |
|---|---:|---:|---:|
| `GROUP BY customer_id` | 948 | 307,808 | 45,568 |
| `GROUP BY order_id` | 20,000 | 310,696 | 366,480 |

*Computed by the book's engine on four simulated nodes on `fixtures/orders-sorted.parquet`, at build time.*
