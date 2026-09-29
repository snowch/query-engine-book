| Step | What it does |
|---|---|
| Compute | `o.order_id AS order_id, c.country AS country, (o.amount / o.quantity) AS unit_price` |
| Join | `o.customer_id = c.customer_id` |
| Select | `((o.amount / o.quantity) > 100)` |
| Get | `fixtures/orders-sorted.parquet: order_id, customer_id, quantity, amount` |
| Get | `fixtures/customers.parquet: customer_id, country; segment = enterprise` |

*Computed by the book's planner and its rules on `fixtures/orders-sorted.parquet` and `fixtures/customers.parquet`, at build time.*
