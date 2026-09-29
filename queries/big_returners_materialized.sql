-- ch18, Pushing instead of pulling: the same customers, with the returned
-- orders read once and kept, for both consumers to read.
WITH returned AS MATERIALIZED (
    SELECT customer_id, amount
    FROM 'fixtures/orders-sorted.parquet'
    WHERE status = 'returned'
)
SELECT customer_id, sum(amount) AS returned
FROM returned
GROUP BY customer_id
HAVING sum(amount) > (SELECT avg(amount) FROM returned)
ORDER BY customer_id;
