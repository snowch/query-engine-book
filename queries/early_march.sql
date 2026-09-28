-- ch03: the orders of the first two weeks of March. Both predicates compare the date with a
-- constant, so the scan can test them, and the file's statistics can rule out row groups.
SELECT order_id, customer_id, amount
FROM 'fixtures/orders-sorted.parquet'
WHERE order_date >= DATE '2024-03-01'
  AND order_date < DATE '2024-03-15';
