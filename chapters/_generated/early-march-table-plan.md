```diagram
┌───────────────────────────┐
│       READ_PARQUET        │
│    ────────────────────   │
│         Function:         │
│        READ_PARQUET       │
│                           │
│        Projections:       │
│          order_id         │
│        customer_id        │
│           amount          │
│                           │
│          Filters:         │
│ order_date>='2024-03-01': │
│ :DATE AND order_date<'2024│
│     -03-15'::DATE AND     │
│   order_date IS NOT NULL  │
│                           │
│         ~4065 Rows        │
└───────────────────────────┘
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-by-month/`, at build time.*
