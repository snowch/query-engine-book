```diagram
┌───────────────────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_decompress_integ│
│     ral_bigint(#0, 1)     │
│__internal_decompress_integ│
│     ral_integer(#1, 1)    │
│             #2            │
│                           │
│        ~20000 Rows        │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│          ORDER_BY         │
│    ────────────────────   │
│  "orders-shuffled".amount │
│            DESC           │
│ "orders-shuffled".order_id│
│             ASC           │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_compress_integra│
│     l_usmallint(#0, 1)    │
│__internal_compress_integra│
│     l_usmallint(#1, 1)    │
│             #2            │
│                           │
│        ~20000 Rows        │
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
