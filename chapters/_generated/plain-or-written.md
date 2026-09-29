| Query | Plain plan | Bytes read | Hand-written plan | Bytes read |
|---|---|---:|---|---:|
| `returned_unit_price.sql` | Project, Filter, Scan | 497,853 | Project, Filter, Filter, Scan | 302,983 |
| `early_march.sql` | Project, Filter, Scan | 497,853 | Scan | 63,218 |
| `orders_per_customer.sql` | Project, HashAggregate, Scan | 497,853 | HashAggregate, Scan | 174,609 |
| `enterprise_orders.sql` | Project, Filter, HashJoin, Project, Scan, Project, Scan | 515,966 | Project, HashJoin, Filter, Scan, Scan | 301,746 |
| `top_orders.sql` | TopK, Sort, Project, Scan | 534,241 | TopK, Scan | 284,586 |

*Computed by the book's planner and engine on `fixtures/orders-sorted.parquet`, `fixtures/orders-shuffled.parquet` and `fixtures/customers.parquet`, at build time.*
