-- ch05: chapter 3's fortnight of orders, from a table of monthly files,
-- found by a glob
SELECT order_id, customer_id, amount
FROM read_parquet('fixtures/orders-by-month/*/*.parquet')
WHERE order_date >= DATE '2024-03-01'
  AND order_date < DATE '2024-03-15';
