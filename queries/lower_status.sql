-- ch01, problem 1.3: the returned orders over the threshold again, asked for another way.
SELECT order_id, customer_id, amount / quantity AS unit_price
FROM 'fixtures/orders-sorted.parquet'
WHERE lower(status) = 'returned'
  AND amount / quantity > 100;
