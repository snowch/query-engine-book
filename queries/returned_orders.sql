-- ch01, The plan is the map: the returned orders, asked with one predicate.
SELECT order_id, customer_id, amount
FROM 'fixtures/orders-sorted.parquet'
WHERE status = 'returned';
