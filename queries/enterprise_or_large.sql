-- ch12, problem 12.3: the orders of enterprise customers, or any order over
-- 2000, with each customer's country. One condition that reads both tables.
SELECT o.order_id, c.country, o.amount
FROM 'fixtures/orders-sorted.parquet' AS o
JOIN 'fixtures/customers.parquet' AS c ON o.customer_id = c.customer_id
WHERE c.segment = 'enterprise' OR o.amount > 2000;
