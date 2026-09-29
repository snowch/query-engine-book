-- ch08, Joins: each order with its customer's country.
SELECT o.order_id, c.country
FROM 'fixtures/orders-sorted.parquet' AS o
JOIN 'fixtures/customers.parquet' AS c ON o.customer_id = c.customer_id;
