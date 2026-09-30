```diagram
┌───────────────────────────┐
│         PROJECTION        │
│    ────────────────────   │
│          order_id         │
│          with_tax         │
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
│                           │
│          Filters:         │
│ quantity>2 AND quantity IS│
│          NOT NULL         │
│                           │
│         ~4000 Rows        │
└───────────────────────────┘
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
