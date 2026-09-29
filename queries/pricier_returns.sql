-- ch01, a change to try: the price threshold raised to 200
SELECT order_id, customer_id, amount / quantity AS unit_price
FROM 'fixtures/orders-sorted.parquet'
WHERE status = 'returned'
  AND amount / quantity > 200;
