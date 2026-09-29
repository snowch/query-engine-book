-- ch07, Hash aggregation: how many orders each customer placed, and what they
-- spent. The key is a whole number from a small range.
SELECT customer_id, count(*) AS orders, sum(amount) AS spent
FROM 'fixtures/orders-sorted.parquet'
GROUP BY customer_id;
