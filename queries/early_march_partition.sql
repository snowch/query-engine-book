-- ch05: the same fortnight, asked of the month in each file's directory
SELECT order_id, customer_id, amount
FROM read_parquet(
  'fixtures/orders-by-month/*/*.parquet', hive_partitioning = true
)
WHERE month = '2024-03'
  AND order_date < DATE '2024-03-15';
