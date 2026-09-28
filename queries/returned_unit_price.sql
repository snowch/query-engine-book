-- ch01, The plan is the map: returned orders whose unit price was over 100.
-- One predicate DuckDB can hand to the scan, one it cannot, and a projection.
SELECT order_id, customer_id, amount / quantity AS unit_price
FROM 'fixtures/orders-sorted.parquet'
WHERE status = 'returned'
  AND amount / quantity > 100;
