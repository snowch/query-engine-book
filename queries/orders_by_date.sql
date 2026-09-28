-- ch02: the orders in date order, each with the row it sat at in the file
SELECT file_row_number, order_id, order_date, status, amount, note
FROM read_parquet('fixtures/orders-shuffled.parquet', file_row_number = true)
ORDER BY order_date, order_id;
