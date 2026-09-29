| Operator | Rows out, estimated | What it does |
|---|---:|---|
| READ_PARQUET | 338 | Projections: `order_id, customer_id, amount`; Filters: `order_date<'2024-03-15'::DATE AND order_date IS NOT NULL`; File Filters: `(month = '2024-03')`; Scanning Files: `1/12` |

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-by-month/`, at build time.*
