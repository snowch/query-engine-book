```diagram
┌───────────────────────────┐
│         PROJECTION        │
│    ────────────────────   │
│          (#0 = 1)         │
│                           │
│          ~1 Rows          │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│    UNGROUPED_AGGREGATE    │
│    ────────────────────   │
│        Aggregates:        │
│        count_star()       │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│             42            │
│                           │
│         ~4000 Rows        │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│      STREAMING_LIMIT      │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│       PARQUET_SCAN        │
│    ────────────────────   │
│         Function:         │
│        PARQUET_SCAN       │
│                           │
│          Filters:         │
│   status='returned' AND   │
│     status IS NOT NULL    │
│                           │
│         ~4000 Rows        │
└───────────────────────────┘
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
