```diagram
the file                          20,000 rows
  │  PARQUET_SCAN
  │    status='returned' AND status IS NOT NULL
  ▼
                                   1,183 rows
  │  FILTER
  │    ((amount / CAST(quantity AS DOUBLE)) >
  │    100.0)
  ▼
                                     729 rows
  │  PROJECTION
  │    order_id, customer_id, unit_price
  ▼
                                     729 rows
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
