-- ch01, a change to try: shipped orders instead of returned ones
SELECT order_id, customer_id, amount / quantity AS unit_price
FROM 'fixtures/orders-sorted.parquet'
WHERE status = 'shipped'
  AND amount / quantity > 100;
