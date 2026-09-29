-- ch18, Pushing instead of pulling: the customers whose returns add up to
-- more than the average returned order. The returned orders are read by two
-- consumers: the totals and the average.
WITH returned AS (
    SELECT customer_id, amount
    FROM 'fixtures/orders-sorted.parquet'
    WHERE status = 'returned'
)
SELECT customer_id, sum(amount) AS returned
FROM returned
GROUP BY customer_id
HAVING sum(amount) > (SELECT avg(amount) FROM returned)
ORDER BY customer_id;
