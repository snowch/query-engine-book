```diagram
┌───────────────────────────┐
│          ORDER_BY         │
│    ────────────────────   │
│     sum(o.amount) DESC    │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│       HASH_GROUP_BY       │
│    ────────────────────   │
│         Groups: #0        │
│                           │
│        Aggregates:        │
│        count_star()       │
│          sum(#1)          │
│                           │
│        ~10000 Rows        │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│          country          │
│           amount          │
│                           │
│        ~20000 Rows        │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_compress_integra│
│     l_usmallint(#0, 1)    │
│             #1            │
│__internal_compress_integra│
│     l_usmallint(#2, 1)    │
│             #3            │
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
│           amount          ││          country          │
│                           ││                           │
│        ~20000 Rows        ││         ~1000 Rows        │
└───────────────────────────┘└───────────────────────────┘
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet` and `fixtures/customers.parquet`, at build time.*
