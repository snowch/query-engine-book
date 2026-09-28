```text
┌───────────────────────────┐
│         PROJECTION        │
│    ────────────────────   │
│          order_id         │
│        customer_id        │
│         unit_price        │
│                           │
│         ~800 Rows         │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│           FILTER          │
│    ────────────────────   │
│  ((amount / CAST(quantity │
│    AS DOUBLE)) > 100.0)   │
│                           │
│         ~800 Rows         │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│       PARQUET_SCAN        │
│    ────────────────────   │
│         Function:         │
│        PARQUET_SCAN       │
│                           │
│        Projections:       │
│           amount          │
│          quantity         │
│          order_id         │
│        customer_id        │
│                           │
│          Filters:         │
│   status='returned' AND   │
│     status IS NOT NULL    │
│                           │
│         ~4000 Rows        │
└───────────────────────────┘
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
