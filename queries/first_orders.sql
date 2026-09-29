-- ch18, Pushing instead of pulling (problem 18.3): any ten orders.
SELECT order_id, order_date, amount
FROM 'fixtures/orders-sorted.parquet'
LIMIT 10;
