-- ch07: the same aggregates, grouped by a string with a handful of values.
SELECT status, count(*) AS orders, sum(amount) AS spent
FROM 'fixtures/orders-sorted.parquet'
GROUP BY status;
