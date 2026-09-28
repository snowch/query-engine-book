-- ch03, problem 3.3: the largest orders of the year.
SELECT order_id, amount
FROM 'fixtures/orders-sorted.parquet'
WHERE amount > 2400;
