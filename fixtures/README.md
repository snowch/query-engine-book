# Fixtures

Written by `fixtures/generate.py` with pyarrow 18.1.0; described by pyarrow and DuckDB
1.1.2 in the manifest beside each file. Do not edit by hand: change the generator, run
`make fixtures`, and commit the files, the manifests and this page together.

| File | Rows | Row groups | Bytes | Why it exists |
|---|---:|---:|---:|---|
| `orders-sorted.parquet` | 20,000 | 10 | 497,857 | Orders written in date order. Each row group holds a narrow run of dates, so a filter on the date can skip most row groups, and neighbouring rows are neighbours in memory. |
| `orders-shuffled.parquet` | 20,000 | 10 | 534,245 | The same orders in a seeded random order. Every row group spans the whole year, so no filter on the date can skip one: the control for orders-sorted. |
| `orders-paged.parquet` | 20,000 | 1 | 415,368 | The sorted orders in one row group, with a page index and small pages, and a dictionary only for the columns with few distinct values. Its one row group spans the year, so row group statistics can skip nothing; its pages each hold a few weeks, so a reader that uses the page index can skip most of them. |
| `customers.parquet` | 1,000 | 1 | 18,117 | The dimension table orders.customer_id points into: one row per customer, small enough to be the build side of any join. |
