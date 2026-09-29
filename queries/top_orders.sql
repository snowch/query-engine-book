-- ch09, Sorting and top-k: the ten largest orders, from the shuffled file.
SELECT order_id, customer_id, amount
FROM 'fixtures/orders-shuffled.parquet'
ORDER BY amount DESC, order_id
LIMIT 10;
