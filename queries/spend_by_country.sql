-- ch17, Stages and distributed execution: what the customers of each country
-- spent, largest first. A join, an aggregate and a sort: three places where a
-- distributed engine must move rows.
SELECT c.country, count(*) AS orders, sum(o.amount) AS spent
FROM 'fixtures/orders-sorted.parquet' AS o
JOIN 'fixtures/customers.parquet' AS c ON o.customer_id = c.customer_id
GROUP BY c.country
ORDER BY spent DESC;
