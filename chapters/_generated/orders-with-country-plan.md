```diagram
┌───────────────────────────┐
│         PROJECTION        │
│    ────────────────────   │
│          order_id         │
│          country          │
│                           │
│        ~20000 Rows        │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         HASH_JOIN         │
│    ────────────────────   │
│      Join Type: INNER     │
│                           │
│        Conditions:        │
│ customer_id = customer_id ├──────────────┐
│                           │              │
│        Build Min: 1       │              │
│      Build Max: 1000      │              │
│                           │              │
│        ~20000 Rows        │              │
└─────────────┬─────────────┘              │
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│       PARQUET_SCAN        ││       PARQUET_SCAN        │
│    ────────────────────   ││    ────────────────────   │
│         Function:         ││         Function:         │
│        PARQUET_SCAN       ││        PARQUET_SCAN       │
│                           ││                           │
│        Projections:       ││        Projections:       │
│        customer_id        ││        customer_id        │
│          order_id         ││          country          │
│                           ││                           │
│        ~20000 Rows        ││         ~1000 Rows        │
└───────────────────────────┘└───────────────────────────┘
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, at build time.*
