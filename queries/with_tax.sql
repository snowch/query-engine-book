-- ch06, Expressions and vectorised kernels: expressions a planner rewrites before it runs them.
-- A product of constants, a sum it can move to the other side, and a division it cannot.
SELECT order_id, amount * (1 + 20 / 100) AS with_tax
FROM 'fixtures/orders-sorted.parquet'
WHERE amount / quantity > 50 * 2
  AND quantity + 1 > 3;
