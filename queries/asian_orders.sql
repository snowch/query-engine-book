-- ch13, Statistics, cost and join order: the orders of customers in Asian
-- countries, joined in the order a person would write them.
SELECT o.order_id, c.name, n.name AS country
FROM 'fixtures/orders-sorted.parquet' AS o
JOIN 'fixtures/customers.parquet' AS c ON o.customer_id = c.customer_id
JOIN 'fixtures/countries.parquet' AS n ON c.country = n.country
WHERE n.region = 'Asia';
