-- ch04: chapter 3's fortnight of orders, from the same orders in one row
-- group with a page index
SELECT order_id, customer_id, amount
FROM 'fixtures/orders-paged.parquet'
WHERE order_date >= DATE '2024-03-01'
  AND order_date < DATE '2024-03-15';
