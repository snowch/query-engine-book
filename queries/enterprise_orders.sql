-- ch11, From SQL to a logical plan: the pricier orders of enterprise
-- customers, with each customer's country. A condition on each table, both
-- written after the join.
SELECT o.order_id, c.country, o.amount / o.quantity AS unit_price
FROM 'fixtures/orders-sorted.parquet' AS o
JOIN 'fixtures/customers.parquet' AS c ON o.customer_id = c.customer_id
WHERE c.segment = 'enterprise'
  AND o.amount / o.quantity > 100;
