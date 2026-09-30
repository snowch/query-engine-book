```diagram
┌───────────────────────────┐
│         PROJECTION        │
│    ────────────────────   │
│          order_id         │
│            name           │
│          country          │
│                           │
│         ~3333 Rows        │
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
│         ~3333 Rows        │              │
└─────────────┬─────────────┘              │
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│       PARQUET_SCAN        ││         HASH_JOIN         │
│    ────────────────────   ││    ────────────────────   │
│         Function:         ││      Join Type: INNER     │
│        PARQUET_SCAN       ││                           │
│                           ││        Conditions:        │
│        Projections:       ││     country = country     ├──────────────┐
│        customer_id        ││                           │              │
│          order_id         ││                           │              │
│                           ││                           │              │
│        ~20000 Rows        ││         ~166 Rows         │              │
└───────────────────────────┘└─────────────┬─────────────┘              │
                             ┌─────────────┴─────────────┐┌─────────────┴─────────────┐
                             │       PARQUET_SCAN        ││       PARQUET_SCAN        │
                             │    ────────────────────   ││    ────────────────────   │
                             │         Function:         ││         Function:         │
                             │        PARQUET_SCAN       ││        PARQUET_SCAN       │
                             │                           ││                           │
                             │        Projections:       ││        Projections:       │
                             │        customer_id        ││          country          │
                             │          country          ││            name           │
                             │            name           ││                           │
                             │                           ││          Filters:         │
                             │                           ││  region='Asia' AND region │
                             │                           ││         IS NOT NULL       │
                             │                           ││                           │
                             │         ~1000 Rows        ││          ~2 Rows          │
                             └───────────────────────────┘└───────────────────────────┘
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet`, `fixtures/customers.parquet` and `fixtures/countries.parquet`, at build time.*
