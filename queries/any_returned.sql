-- ch18, Pushing instead of pulling: is there a returned order at all? One row
-- answers it.
SELECT EXISTS (
    SELECT 1 FROM 'fixtures/orders-sorted.parquet' WHERE status = 'returned'
) AS any_returned;
