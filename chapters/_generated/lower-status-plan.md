```text
┌───────────────────────────┐
│         PROJECTION        │
│    ────────────────────   │
│          order_id         │
│        customer_id        │
│         unit_price        │
│                           │
│         ~4000 Rows        │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│           FILTER          │
│    ────────────────────   │
│ (((amount / CAST(quantity │
│  AS DOUBLE)) > 100.0) AND │
│ (lower(status) = 'returned│
│            '))            │
│                           │
│         ~4000 Rows        │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│       PARQUET_SCAN        │
│    ────────────────────   │
│         Function:         │
│        PARQUET_SCAN       │
│                           │
│        Projections:       │
│           status          │
│           amount          │
│          quantity         │
│          order_id         │
│        customer_id        │
│                           │
│        ~20000 Rows        │
└───────────────────────────┘
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
