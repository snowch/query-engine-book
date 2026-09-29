```diagram
┌───────────────────────────┐
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
│          Filters:         │
│   status='returned' AND   │
│     status IS NOT NULL    │
│                           │
│         ~4000 Rows        │
└───────────────────────────┘
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
