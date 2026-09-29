-- ch18, Pushing instead of pulling (problem 18.3): the ten earliest orders.
SELECT order_id, order_date, amount
FROM 'fixtures/orders-sorted.parquet'
ORDER BY order_date, order_id
LIMIT 10;
