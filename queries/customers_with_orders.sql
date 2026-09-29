-- ch08: the same join, written with the customers first.
SELECT o.order_id, c.country
FROM 'fixtures/customers.parquet' AS c
JOIN 'fixtures/orders-sorted.parquet' AS o ON o.customer_id = c.customer_id;
