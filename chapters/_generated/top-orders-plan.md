```diagram
┌───────────────────────────┐
│           TOP_N           │
│    ────────────────────   │
│          Top: 10          │
│                           │
│         Order By:         │
│  "orders-shuffled".amount │
│            DESC           │
│ "orders-shuffled".order_id│
│             ASC           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│       PARQUET_SCAN        │
│    ────────────────────   │
│         Function:         │
│        PARQUET_SCAN       │
│                           │
│        Projections:       │
│          order_id         │
│        customer_id        │
│           amount          │
│                           │
│        ~20000 Rows        │
└───────────────────────────┘
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-shuffled.parquet`, at build time.*
