-- ch09: every order, largest first: the same query with no LIMIT.
SELECT order_id, customer_id, amount
FROM 'fixtures/orders-shuffled.parquet'
ORDER BY amount DESC, order_id;
