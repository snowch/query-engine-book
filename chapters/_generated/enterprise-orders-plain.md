| Step | What it does |
|---|---|
| Compute | `o.order_id AS order_id, c.country AS country, (o.amount / o.quantity) AS unit_price` |
| Select | `((c.segment = 'enterprise') and ((o.amount / o.quantity) > 100))` |
| Join | `o.customer_id = c.customer_id` |
| Get | `fixtures/orders-sorted.parquet: order_id, order_date, customer_id, status, quantity, amount, note` |
| Get | `fixtures/customers.parquet: customer_id, name, country, segment, signup_date` |

*Computed by the book's planner on `fixtures/orders-sorted.parquet` and `fixtures/customers.parquet`, at build time.*
