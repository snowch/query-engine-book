```diagram
┌───────────────────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_decompress_integ│
│     ral_bigint(#0, 0)     │
│__internal_decompress_integ│
│     ral_bigint(#1, 1)     │
│             #2            │
│             #3            │
│             #4            │
│             #5            │
│                           │
│        ~20000 Rows        │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│          ORDER_BY         │
│    ────────────────────   │
│read_parquet.order_date ASC│
│ read_parquet.order_id ASC │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         PROJECTION        │
│    ────────────────────   │
│__internal_compress_integra│
│     l_usmallint(#0, 0)    │
│__internal_compress_integra│
│     l_usmallint(#1, 1)    │
│             #2            │
│             #3            │
│             #4            │
│             #5            │
│                           │
│        ~20000 Rows        │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│       READ_PARQUET        │
│    ────────────────────   │
│         Function:         │
│        READ_PARQUET       │
│                           │
│        Projections:       │
│      file_row_number      │
│          order_id         │
│         order_date        │
│           status          │
│           amount          │
│            note           │
│                           │
│        ~20000 Rows        │
└───────────────────────────┘
```

*Computed by DuckDB 1.1.2 with one thread on `fixtures/orders-shuffled.parquet`, at build time.*
