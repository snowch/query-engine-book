-- ch18, Pushing instead of pulling: how many returned orders are there? Every
-- row counts.
SELECT count(*) AS returned
FROM 'fixtures/orders-sorted.parquet'
WHERE status = 'returned';
