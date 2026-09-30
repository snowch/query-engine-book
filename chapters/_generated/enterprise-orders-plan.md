```diagram
┌───────────────────────────┐
│         PROJECTION        │
│    ────────────────────   │
│          order_id         │
│          country          │
│         unit_price        │
│                           │
│         ~800 Rows         │
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
│         ~800 Rows         │              │
└─────────────┬─────────────┘              │
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│           FILTER          ││       PARQUET_SCAN        │
│    ────────────────────   ││    ────────────────────   │
│  ((amount / CAST(quantity ││         Function:         │
│    AS DOUBLE)) > 100.0)   ││        PARQUET_SCAN       │
│                           ││                           │
│                           ││        Projections:       │
│                           ││        customer_id        │
│                           ││          country          │
│                           ││                           │
│                           ││          Filters:         │
│                           ││  segment='enterprise' AND │
│                           ││     segment IS NOT NULL   │
│                           ││                           │
│         ~4000 Rows        ││         ~200 Rows         │
└─────────────┬─────────────┘└───────────────────────────┘
┌─────────────┴─────────────┐
│       PARQUET_SCAN        │
│    ────────────────────   │
│         Function:         │
│        PARQUET_SCAN       │
│                           │
│        Projections:       │
│        customer_id        │
│           amount          │
│          quantity         │
│          order_id         │
│                           │
│        ~20000 Rows        │
└───────────────────────────┘
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet` and `fixtures/customers.parquet`, at build time.*
