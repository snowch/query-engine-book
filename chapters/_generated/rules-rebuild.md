| Query | Your rules' plan, bytes read | Hand-written plan, bytes read |
|---|---:|---:|
| `returned_unit_price.sql` | 302,983 | 302,983 |
| `early_march.sql` | 63,218 | 63,218 |
| `early_march_paged.sql` | 214,796 | 18,683 |
| `largest_orders.sql` | 242,916 | 242,916 |
| `with_tax.sql` | 254,056 | 254,056 |
| `orders_per_customer.sql` | 174,609 | 174,609 |
| `orders_per_status.sql` | 142,996 | 142,996 |
| `orders_with_country.sql` | 163,358 | 163,358 |
| `customers_with_orders.sql` | 163,358 | 163,358 |
| `top_orders.sql` | 284,586 | 284,586 |
| `orders_by_amount.sql` | 284,586 | 284,586 |
| `enterprise_orders.sql` | 301,746 | 301,746 |

*Computed by the book's planner and rules on `fixtures/orders-sorted.parquet`, `fixtures/orders-paged.parquet`, `fixtures/orders-shuffled.parquet` and `fixtures/customers.parquet`, at build time.*
