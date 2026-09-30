```diagram
┌───────────────────────────┐
│         PROJECTION        │
│    ────────────────────   │
│        Expressions:       │
│          order_id         │
│          country          │
│         unit_price        │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│           FILTER          │
│    ────────────────────   │
│        Expressions:       │
│      (segment = CAST(     │
│ 'enterprise' AS VARCHAR)) │
│  ((amount / CAST(quantity │
│  AS DOUBLE)) > CAST(100 AS│
│          DOUBLE))         │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│      COMPARISON_JOIN      │
│    ────────────────────   │
│      Join Type: INNER     │
│                           ├──────────────┐
│        Conditions:        │              │
│(customer_id = customer_id)│              │
└─────────────┬─────────────┘              │
┌─────────────┴─────────────┐┌─────────────┴─────────────┐
│        PARQUET_SCAN       ││        PARQUET_SCAN       │
│    ────────────────────   ││    ────────────────────   │
└───────────────────────────┘└───────────────────────────┘
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-sorted.parquet` and `fixtures/customers.parquet`, at build time.*
