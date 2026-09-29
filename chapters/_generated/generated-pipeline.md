```python
def pipeline(batch, out):
    amount = batch.column('amount').to_pylist()
    customer_id = batch.column('customer_id').to_pylist()
    order_id = batch.column('order_id').to_pylist()
    quantity = batch.column('quantity').to_pylist()
    status = batch.column('status').to_pylist()
    for i in range(batch.num_rows):
        if not (status[i] == 'returned'):
            continue
        v0 = divide(amount[i], quantity[i])
        if not (v0 > 100):
            continue
        out['order_id'].append(order_id[i])
        out['customer_id'].append(customer_id[i])
        out['unit_price'].append(v0)
```

*Written by the book's compiler from `queries/returned_unit_price.sql`, at build time.*
