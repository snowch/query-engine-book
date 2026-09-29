"""What each chapter's measure panel shows: one function per panel, from ch07 on.

A measure panel asks the reader to predict one number for each of a few cases, then reveals what
the engine counted, beside a reference the prediction can be judged against, and may draw a chart
of the same measurement across a range of settings. ``query_lab.report.measure`` runs the function
a lab block names; ``web/lab/measure.js`` draws what it returns. Each function returns:

- ``title``, the panel's title, and ``predict``: ``label`` (what the measured bar is),
  ``ask`` (what the title asks for) and ``placeholder`` (the prediction box's hint);
- ``facts``, one sentence of what the reader predicts from;
- ``cases``: each with a ``label``, a ``detail`` shown as code, a ``reference`` (``label`` and
  ``value``), the ``measured`` value, and ``counters``, pairs of a name and a number;
- optionally ``chart``: ``x_label``, ``y_label``, ``x_scale`` (``linear`` or ``log``) and
  ``series``, each a ``label`` and ``points``, pairs of numbers.

The engine needs pyarrow, which the plan panel does not load in the page, so each function
imports what it uses.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

#: The keys the aggregation panel groups the sorted orders by, from fewest groups to most.
GROUP_KEYS = ("status", "customer_id", "order_id")
#: The numbers of groups the aggregation panel's chart sweeps: the order ids folded onto so many.
GROUP_SWEEP = (4, 16, 64, 256, 512, 1024, 2048, 4096, 8192, 20_000)


def aggregation(root: Path) -> dict:
    """The sorted orders grouped by three keys through the hash table and the cache model, then
    the order ids folded onto more and more groups, through a hash table and a perfect one."""
    from .aggregate import HashTable, PerfectTable
    from .cache import LINE_BYTES, LINES, Cache
    from .operators import Scan

    table = Scan(root / "fixtures" / "orders-sorted.parquet", list(GROUP_KEYS)).run()
    cases = []
    for key in GROUP_KEYS:
        values = table.column(key).to_pylist()
        cache = Cache()
        hashed = HashTable(cache=cache)
        for v in values:
            hashed.find(v)
        c = hashed.counters()
        cases.append(
            {
                "label": f"GROUP BY {key}",
                "detail": f"{c['groups']:,} groups",
                "reference": {"label": "Rows", "value": len(values)},
                "measured": cache.misses,
                "counters": [
                    ["groups", c["groups"]],
                    ["probes", c["probes"]],
                    ["resizes", c["resizes"]],
                    ["table bytes", c["table_bytes"]],
                ],
            }
        )
    ids = table.column("order_id").to_pylist()
    hashed_points, perfect_points = [], []
    for groups in GROUP_SWEEP:
        keys = [i % groups for i in ids]
        for make, points in ((lambda c: HashTable(cache=c), hashed_points), (None, perfect_points)):
            cache = Cache()
            t = make(cache) if make else PerfectTable(0, groups - 1, cache=cache)
            for k in keys:
                t.find(k)
            points.append([groups, cache.misses])
    return {
        "title": "Grouping the orders",
        "predict": {
            "label": "Cache misses",
            "ask": "the cache misses of each",
            "placeholder": "cache misses",
        },
        "facts": (
            f"Each slot of the hash table takes 16 bytes, and the table doubles when three quarters "
            f"full. The cache holds {LINES:,} lines of {LINE_BYTES} bytes."
        ),
        "cases": cases,
        "chart": {
            "x_label": "groups",
            "y_label": "cache misses",
            "x_scale": "log",
            "series": [
                {"label": "Hash table", "points": hashed_points},
                {"label": "Perfect hash table", "points": perfect_points},
            ],
        },
    }


#: The sizes of the build side the join panel's chart sweeps, in rows.
BUILD_SWEEP = (256, 512, 1024, 2048, 4096, 8192, 16_384, 20_000)


def joins(root: Path) -> dict:
    """The orders joined with their customers three ways through the cache model: built on the
    customers, built on the orders, and built on the customers a filter keeps. Then a build side
    of more and more orders, probed by every order in random order."""
    from .aggregate import HashTable
    from .cache import LINE_BYTES, LINES, Cache
    from .join import HashJoin
    from .operators import Comparison, Scan

    fixtures = root / "fixtures"
    orders = lambda: Scan(fixtures / "orders-sorted.parquet", ["order_id", "customer_id"])  # noqa: E731

    def customers(filters=()):
        return Scan(fixtures / "customers.parquet", ["customer_id", "country"], filters=list(filters))

    ways = [
        (
            "Build on the customers",
            "customers: 1 row each",
            lambda t: HashJoin(
                orders(),
                customers(),
                "customer_id",
                "customer_id",
                [("probe", "order_id"), ("build", "country")],
                t,
            ),
        ),
        (
            "Build on the orders",
            "orders: many rows per customer",
            lambda t: HashJoin(
                customers(),
                orders(),
                "customer_id",
                "customer_id",
                [("build", "order_id"), ("probe", "country")],
                t,
            ),
        ),
        (
            "Build on enterprise customers",
            "segment = 'enterprise'",
            lambda t: HashJoin(
                orders(),
                customers([Comparison("segment", "=", "enterprise")]),
                "customer_id",
                "customer_id",
                [("probe", "order_id"), ("build", "country")],
                t,
            ),
        ),
    ]
    cases = []
    for label, detail, make in ways:
        cache = Cache()
        join = make(HashTable(cache=cache))
        rows = join.run().num_rows
        cases.append(
            {
                "label": label,
                "detail": detail,
                "reference": {"label": "Rows joined", "value": rows},
                "measured": cache.misses,
                "counters": [
                    ["build rows", join.build_rows],
                    ["held bytes", join.held_bytes],
                    ["probes", join.table.probes],
                ],
            }
        )
    ids = Scan(fixtures / "orders-shuffled.parquet", ["order_id"]).run().column("order_id").to_pylist()
    points = []
    for n in BUILD_SWEEP:
        cache = Cache()
        table = HashTable(cache=cache)
        for key in range(1, n + 1):
            table.find(key)
        before = cache.misses
        for key in ids:
            group = table.get(key)
            if group is not None:
                cache.read("build rows", group * 16, 16)
        points.append([n, cache.misses - before])
    return {
        "title": "Joining the orders and their customers",
        "predict": {
            "label": "Cache misses",
            "ask": "the cache misses of each",
            "placeholder": "cache misses",
        },
        "facts": (
            f"The join holds its build side: a table of 16-byte slots, and each row at 8 bytes a column "
            f"plus 8. The cache holds {LINES:,} lines of {LINE_BYTES} bytes."
        ),
        "cases": cases,
        "chart": {
            "x_label": "build rows",
            "y_label": "cache misses while probing",
            "x_scale": "log",
            "series": [{"label": "Every order probing a build side of that many orders", "points": points}],
        },
    }


#: The numbers of rows the sorting panel's chart asks a top-k to keep.
TOP_SWEEP = (1, 10, 100, 1000, 5000, 10_000, 20_000)


def sorting(root: Path) -> dict:
    """Three orders the orders can be put in, counting comparisons: the shuffled orders by amount,
    the sorted orders by date, and the ten largest by amount. Then a top-k of more and more rows,
    beside a full sort."""
    from . import plans
    from .operators import Scan
    from .sort import Sort, TopK

    fixtures = root / "fixtures"
    shuffled = lambda: Scan(fixtures / "orders-shuffled.parquet", ["order_id", "amount"])  # noqa: E731
    ways = [
        (
            "Sort the shuffled orders by amount",
            "ORDER BY amount DESC, order_id",
            lambda: Sort(shuffled(), plans.BY_AMOUNT),
        ),
        (
            "Sort the orders by date, as stored",
            "ORDER BY order_date, order_id",
            lambda: Sort(
                Scan(fixtures / "orders-sorted.parquet", ["order_id", "order_date"]),
                [("order_date", False), ("order_id", False)],
            ),
        ),
        (
            "The ten largest by amount",
            "ORDER BY amount DESC, order_id LIMIT 10",
            lambda: TopK(shuffled(), plans.BY_AMOUNT, 10),
        ),
    ]
    cases = []
    for label, detail, make in ways:
        op = make()
        op.run()
        cases.append(
            {
                "label": label,
                "detail": detail,
                "reference": {"label": "Rows", "value": op.metrics.rows_in},
                "measured": op.comparisons.count,
                "counters": [["rows held", op.rows_held], ["rows handed up", op.metrics.rows_out]],
            }
        )
    full = cases[0]["measured"]
    heap = []
    scan = shuffled()
    batches = list(scan.batches())
    for k in TOP_SWEEP:
        op = TopK(_replay(batches, scan.schema()), plans.BY_AMOUNT, k)
        op.run()
        heap.append([k, op.comparisons.count])
    return {
        "title": "Putting the orders in order",
        "predict": {"label": "Comparisons", "ask": "the comparisons of each", "placeholder": "comparisons"},
        "facts": (
            "A full sort holds every row and sorts them with Python's own sort; the top-k holds the "
            "best rows so far in a heap and compares each new row with the worst of them."
        ),
        "cases": cases,
        "chart": {
            "x_label": "rows the top-k keeps",
            "y_label": "comparisons",
            "x_scale": "log",
            "series": [
                {"label": "Top-k in a heap", "points": heap},
                {"label": "A full sort", "points": [[k, full] for k in TOP_SWEEP]},
            ],
        },
    }


#: The memory limits the spilling panel's chart sorts the orders within, as shares of the rows'
#: bytes, and the fan-ins it merges with.
SPILL_SHARES = (0.1, 0.2, 0.5, 1.0)
SPILL_FAN_INS = (2, 8)


def _replay(batches: list, schema):
    """An operator that hands up ``batches`` again, from memory: a panel that sorts the same rows
    many times reads the file once."""
    from .operators import Operator

    class Replay(Operator):
        def __init__(self) -> None:
            super().__init__("Replay", "the scan's batches", [])

        def batches(self):
            for batch in batches:
                yield self.emit(batch)

        def schema(self):
            return schema

    return Replay()


def spilling(root: Path) -> dict:
    """The shuffled orders sorted by amount within three memory limits, counting the bytes the sort
    spilled; then the same sort within more limits, with a small fan-in and a larger one."""
    from . import plans
    from .spill import ExternalSort

    scan = plans.orders_by_amount(root).child
    batches = list(scan.batches())
    total = sum(b.get_total_buffer_size() for b in batches)
    runs = {}
    for fan_in in SPILL_FAN_INS:
        for share in SPILL_SHARES:
            op = ExternalSort(
                _replay(batches, scan.schema()), plans.BY_AMOUNT, int(total * share) + 1, fan_in
            )
            op.run()
            runs[fan_in, share] = op
    cases = []
    for label, key in (
        ("Memory for every row", (8, 1.0)),
        ("Memory for half the rows", (8, 0.5)),
        ("A tenth, merging two runs at a time", (2, 0.1)),
    ):
        op = runs[key]
        cases.append(
            {
                "label": label,
                "detail": f"memory limit {op.memory_limit:,} bytes, fan-in {op.fan_in}",
                "reference": {"label": "Bytes of rows", "value": total},
                "measured": op.temp.written,
                "counters": [
                    ["runs written", op.sorted_runs + op.merged_runs],
                    ["merge passes", op.passes],
                    ["bytes read back", op.temp.read],
                ],
            }
        )
    return {
        "title": "Sorting within a memory limit",
        "predict": {"label": "Bytes spilled", "ask": "the bytes each spills", "placeholder": "bytes spilled"},
        "facts": (
            f"The rows to sort take {total:,} bytes, in batches of a tenth of that. A run is spilled as "
            "Arrow IPC, which adds a little to its rows' bytes."
        ),
        "cases": cases,
        "chart": {
            "x_label": "the memory limit, in bytes",
            "y_label": "bytes spilled",
            "x_scale": "log",
            "series": [
                {
                    "label": f"Fan-in {fan_in}",
                    "points": [
                        [runs[fan_in, share].memory_limit, runs[fan_in, share].temp.written]
                        for share in SPILL_SHARES
                    ],
                }
                for fan_in in SPILL_FAN_INS
            ],
        },
    }


#: The queries the planning panel plans the plain way, beside the plans earlier chapters wrote.
PLAIN_QUERIES = ("returned_unit_price.sql", "early_march.sql", "enterprise_orders.sql")
#: The days the planning panel's chart widens early March to, counted from the first of March.
WINDOW_DAYS = (1, 7, 30, 91, 245)


def planning(root: Path) -> dict:
    """Three of the book's queries planned the plain way, counting the bytes each reads, beside
    the plans earlier chapters wrote by hand. Then the orders from the first of March, over a
    wider and wider window, planned both ways."""
    import datetime as dt

    from . import plans
    from .operators import Comparison, Scan
    from .planner import plan
    from .reference import read_query

    def run(operator):
        operator.run()
        scans = [m for m in operator.metrics.walk() if m.operator == "Scan"]
        return sum(m.bytes_read for m in scans), sum(m.rows_out for m in scans)

    cases = []
    for query in PLAIN_QUERIES:
        plain = plan(root, read_query(root / "queries" / query))
        read, rows = run(plain)
        written, _ = run(plans.plan_for(root, query))
        cases.append(
            {
                "label": query.removesuffix(".sql"),
                "detail": f"queries/{query}",
                "reference": {"label": "Hand-written plan", "value": written},
                "measured": read,
                "counters": [
                    ["rows the scans hand up", rows],
                    ["operators", sum(1 for _ in plain.metrics.walk())],
                ],
            }
        )
    first = dt.date(2024, 3, 1)
    plain_points, written_points = [], []
    for days in WINDOW_DAYS:
        last = first + dt.timedelta(days=days)
        text = (
            "SELECT order_id, customer_id, amount FROM 'fixtures/orders-sorted.parquet' "
            f"WHERE order_date >= DATE '{first}' AND order_date < DATE '{last}'"
        )
        plain_points.append([days, run(plan(root, text))[0]])
        window = [Comparison("order_date", ">=", first), Comparison("order_date", "<", last)]
        scan = Scan(
            root / "fixtures" / "orders-sorted.parquet", ["order_id", "customer_id", "amount"], window
        )
        written_points.append([days, run(scan)[0]])
    return {
        "title": "What the plain plan reads",
        "predict": {
            "label": "Bytes read",
            "ask": "the bytes each plain plan reads",
            "placeholder": "bytes read",
        },
        "facts": (
            "The plain plan reads every column of every table the query names, and tests its "
            "conditions after the scan. The hand-written plans read only the columns they use, and "
            "test what they can inside the scan."
        ),
        "cases": cases,
        "chart": {
            "x_label": "days from the first of March",
            "y_label": "bytes read",
            "x_scale": "log",
            "series": [
                {"label": "Plain plan", "points": plain_points},
                {"label": "Hand-written plan", "points": written_points},
            ],
        },
    }


def rules(root: Path) -> dict:
    """ch11's enterprise orders planned the plain way, then with each of ch12's first two rules
    alone and with both, counting the bytes read and the rows that reach the join."""
    from .planner import plan
    from .reference import read_query
    from .rules import prune_columns, push_filters

    text = read_query(root / "queries" / "enterprise_orders.sql")

    def run(rules: tuple):
        operator = plan(root, text, rules)
        operator.run()
        walk = list(operator.metrics.walk())
        join = next(m for m in walk if m.operator == "HashJoin")
        scans = [m for m in walk if m.operator == "Scan"]
        return sum(m.bytes_read for m in scans), sum(m.rows_out for m in scans), join.rows_in

    plain, _, _ = run(())
    cases = []
    for label, chosen in (
        ("Push the filters down", (push_filters,)),
        ("Prune the columns", (prune_columns,)),
        ("Both rules", (push_filters, prune_columns)),
    ):
        read, scanned, joined = run(chosen)
        cases.append(
            {
                "label": label,
                "detail": ", then ".join(r.__name__ for r in chosen),
                "reference": {"label": "The plain plan", "value": plain},
                "measured": read,
                "counters": [["rows from the scans", scanned], ["rows into the join", joined]],
            }
        )
    return {
        "title": "Two rules, one at a time",
        "predict": {"label": "Bytes read", "ask": "the bytes each plan reads", "placeholder": "bytes read"},
        "facts": (
            "The query keeps enterprise customers, a quarter of them, and orders over a unit price, "
            "from two tables of seven and five columns. The customers are one row group."
        ),
        "cases": cases,
    }


def _operators(root, name: str) -> list:
    """Every operator in a plan called ``name``, top down."""
    found = [root] if root.metrics.operator == name else []
    for child in root.children:
        found += _operators(child, name)
    return found


#: The amounts the cost panel's chart asks ``amount > x`` of, to set the estimate beside the count.
AMOUNT_SWEEP = (100, 250, 500, 1000, 1500, 2000, 2400)


def join_orders(root: Path) -> dict:
    """ch13's three-table query joined in three orders, counting the rows the joins hand up, beside
    the planner's estimate of each; then ``amount > x`` estimated from the footer and counted."""
    from .cost import joined_rows, selectivity, table_stats
    from .operators import Comparison, Scan
    from .planner import Join, logical_plan, physical_plan
    from .reference import read_query
    from .rules import prune_columns, push_filters
    from .sql import parse

    text = read_query(root / "queries" / "asian_orders.sql")
    written = push_filters(logical_plan(root, parse(text)))
    compute = written
    joins = compute.children[0]
    (inner, n), (o, c) = joins.children, joins.children[0].children
    orders_first = Join(children=[inner, n], left_key="c.country", right_key="n.country")
    customers_first = Join(
        children=[o, Join(children=[c, n], left_key="c.country", right_key="n.country")],
        left_key="o.customer_id",
        right_key="c.customer_id",
    )
    built_on_orders = Join(
        children=[Join(children=[c, n], left_key="c.country", right_key="n.country"), o],
        left_key="c.customer_id",
        right_key="o.customer_id",
    )
    cases = []
    for label, detail, joined in (
        ("Orders with customers, then countries", "as the query is written", orders_first),
        ("Customers with countries, then orders", "the smaller join first", customers_first),
        ("The same, built on the orders", "the larger side held", built_on_orders),
    ):
        plan = prune_columns(type(compute)(children=[joined], items=compute.items))
        operator = physical_plan(root, plan)
        operator.run()
        hash_joins = [m for m in operator.metrics.walk() if m.operator == "HashJoin"]
        held = _operators(operator, "HashJoin")
        cases.append(
            {
                "label": label,
                "detail": detail,
                "reference": {"label": "The planner's estimate", "value": round(joined_rows(root, plan))},
                "measured": sum(m.rows_out for m in hash_joins),
                "counters": [
                    ["rows into the joins", sum(m.rows_in for m in hash_joins)],
                    ["build rows held", sum(j.build_rows for j in held)],
                ],
            }
        )
    orders = root / "fixtures" / "orders-sorted.parquet"
    stats = table_stats(orders)
    amounts = Scan(orders, ["amount"]).run().column("amount").to_pylist()
    estimated, counted = [], []
    for x in AMOUNT_SWEEP:
        estimated.append(
            [x, round(stats.rows * selectivity(Comparison("amount", ">", float(x)), stats.columns))]
        )
        counted.append([x, sum(1 for a in amounts if a > x)])
    return {
        "title": "Three ways to join three tables",
        "predict": {
            "label": "Rows the joins hand up",
            "ask": "the rows each order's joins hand up, added together",
            "placeholder": "rows",
        },
        "facts": (
            "There are twenty thousand orders, a thousand customers and twelve countries, two of them "
            "in Asia. Every order has a customer and every customer a country."
        ),
        "cases": cases,
        "chart": {
            "x_label": "x, in amount > x",
            "y_label": "rows",
            "x_scale": "linear",
            "series": [
                {"label": "Estimated from the footer", "points": estimated},
                {"label": "Counted", "points": counted},
            ],
        },
    }


#: The workers the parallelism panel's chart runs each pipeline with.
WORKER_SWEEP = (1, 2, 3, 4, 6, 8, 12, 16)


def parallelism(root: Path) -> dict:
    """Two pipelines run by four simulated workers on the sorted orders, and one on the same
    orders in a single row group, counting the work until each query is done; then the speedup of
    each as the workers grow."""
    from .parallel import PER_CUSTOMER, RETURNED, run

    fixtures = root / "fixtures"
    ways = [
        (
            "ch01's returned orders",
            "orders-sorted: a filter and a projection",
            fixtures / "orders-sorted.parquet",
            RETURNED,
        ),
        (
            "ch07's orders per customer",
            "orders-sorted: an aggregate",
            fixtures / "orders-sorted.parquet",
            PER_CUSTOMER,
        ),
        (
            "The returned orders, one row group",
            "orders-paged: the same pipeline",
            fixtures / "orders-paged.parquet",
            RETURNED,
        ),
    ]
    cases, series = [], []
    for label, detail, path, (columns, pipeline, keys) in ways:
        four = run(path, columns, pipeline, 4, keys)
        cases.append(
            {
                "label": label,
                "detail": detail,
                "reference": {"label": "Work on one worker", "value": four.total},
                "measured": four.finished,
                "counters": [
                    ["morsels", len(four.morsels)],
                    ["busiest worker's work", max(four.workers)],
                    ["work combining the workers' tables", four.after],
                ],
            }
        )
        series.append(
            {
                "label": label,
                "points": [
                    [w, round(run(path, columns, pipeline, w, keys).speedup, 2)] for w in WORKER_SWEEP
                ],
            }
        )
    return {
        "title": "Four workers",
        "predict": {
            "label": "Work until done",
            "ask": "the work before each query is done, with four workers",
            "placeholder": "rows of work",
        },
        "facts": (
            "A morsel is one row group. The sorted orders are ten row groups of equal size; the paged "
            "orders are one. Work is the rows each operator takes in. Each worker takes the next morsel "
            "when it is free."
        ),
        "cases": cases,
        "chart": {"x_label": "workers", "y_label": "speedup", "x_scale": "linear", "series": series},
    }


#: The nodes the shuffle panel's chart spreads the tables over.
NODE_SWEEP = (2, 4, 8, 16, 32, 64)


def shuffle(root: Path) -> dict:
    """The orders per customer and the orders with their country, each done two ways on four
    simulated nodes, counting the bytes sent between nodes; then the joins on more nodes."""
    import pyarrow.parquet as pq

    from . import distributed as d

    fixtures = root / "fixtures"

    def spread(nodes: int):
        orders = d.place(fixtures / "orders-sorted.parquet", ["order_id", "customer_id", "amount"], nodes)
        customers = pq.read_table(fixtures / "customers.parquet", columns=["customer_id", "country"])
        return orders, customers

    orders, customers = spread(4)
    ids = [t.select(["order_id", "customer_id"]) for t in orders]
    held = d.place(fixtures / "customers.parquet", ["customer_id", "country"], 4)
    rows = sum(d.ipc_bytes(t) for t in orders)
    cases = []
    for label, detail, result, of in (
        (
            "Aggregate after shuffling every order",
            "GROUP BY customer_id",
            d.aggregate_after_shuffle(orders),
            rows,
        ),
        ("Aggregate in two phases", "GROUP BY customer_id", d.aggregate_in_two_phases(orders), rows),
        ("Join, shuffling both sides", "orders JOIN customers", d.join_by_shuffle(ids, held), None),
        (
            "Join, broadcasting the customers",
            "orders JOIN customers",
            d.join_by_broadcast(ids, customers),
            None,
        ),
    ):
        reference = of if of is not None else sum(d.ipc_bytes(t) for t in ids) + d.ipc_bytes(customers)
        cases.append(
            {
                "label": label,
                "detail": detail,
                "reference": {"label": "Bytes of the rows", "value": reference},
                "measured": result.shuffled,
                "counters": [["rows out", result.table().num_rows]],
            }
        )
    shuffled, broadcast = [], []
    for nodes in NODE_SWEEP:
        orders, customers = spread(nodes)
        ids = [t.select(["order_id", "customer_id"]) for t in orders]
        held = d.place(fixtures / "customers.parquet", ["customer_id", "country"], nodes)
        shuffled.append([nodes, d.join_by_shuffle(ids, held).shuffled])
        broadcast.append([nodes, d.join_by_broadcast(ids, customers).shuffled])
    return {
        "title": "Four nodes",
        "predict": {
            "label": "Bytes shuffled",
            "ask": "the bytes each sends between nodes",
            "placeholder": "bytes",
        },
        "facts": (
            "The orders' row groups are dealt out to the nodes in turn. The customers are one row "
            "group, on one node. A row costs its Arrow IPC bytes to send, and nothing to keep."
        ),
        "cases": cases,
        "chart": {
            "x_label": "nodes",
            "y_label": "bytes shuffled by the join",
            "x_scale": "linear",
            "series": [
                {"label": "Shuffling both sides", "points": shuffled},
                {"label": "Broadcasting the customers", "points": broadcast},
            ],
        },
    }


#: The nodes the skew panel's chart spreads the join over.
SKEW_NODES = (2, 4, 8, 16, 32)


def skew(root: Path) -> dict:
    """ch15's join of the orders and their customers on sixteen simulated nodes, three ways,
    counting the rows the busiest node joins; then the plain and the salted shuffle on more
    nodes."""
    import pyarrow.parquet as pq

    from . import distributed as d
    from .skew import busiest, join_salted

    fixtures = root / "fixtures"
    customers = pq.read_table(fixtures / "customers.parquet", columns=["customer_id", "country"])

    def spread(nodes: int):
        orders = d.place(fixtures / "orders-sorted.parquet", ["order_id", "customer_id"], nodes)
        return orders, d.place(fixtures / "customers.parquet", ["customer_id", "country"], nodes)

    nodes = 16
    orders, held = spread(nodes)
    even = sum(t.num_rows for t in orders) // nodes
    cases = []
    for label, detail, result in (
        ("Shuffled by customer", "ch15's shuffle join", d.join_by_shuffle(orders, held)),
        (
            "The heaviest customers salted",
            f"their orders spread over {nodes} nodes",
            join_salted(orders, held, nodes),
        ),
        ("The customers broadcast", "the orders stay where they are", d.join_by_broadcast(orders, customers)),
    ):
        cases.append(
            {
                "label": label,
                "detail": detail,
                "reference": {"label": "An even share", "value": even},
                "measured": busiest(result.parts),
                "counters": [["bytes shuffled", result.shuffled], ["rows out", result.table().num_rows]],
            }
        )
    plain, salted, shares = [], [], []
    for n in SKEW_NODES:
        orders, held = spread(n)
        plain.append([n, busiest(d.join_by_shuffle(orders, held).parts)])
        salted.append([n, busiest(join_salted(orders, held, n).parts)])
        shares.append([n, sum(t.num_rows for t in orders) // n])
    return {
        "title": "Sixteen nodes, one heavy customer",
        "predict": {
            "label": "Rows on the busiest node",
            "ask": "the rows the busiest node joins",
            "placeholder": "rows",
        },
        "facts": (
            "The heaviest customer placed about a fifth of the orders, and the next few many more than "
            "their share. The orders are ten row groups, dealt out to the nodes in turn."
        ),
        "cases": cases,
        "chart": {
            "x_label": "nodes",
            "y_label": "rows on the busiest node",
            "x_scale": "log",
            "series": [
                {"label": "Shuffled by customer", "points": plain},
                {"label": "Salted", "points": salted},
                {"label": "An even share", "points": shares},
            ],
        },
    }


def stages(root: Path) -> dict:
    """ch17's query in four stages on sixteen simulated nodes, one node failing in the third
    stage, with the shuffled rows kept three ways; then a failure in each stage."""
    from . import stages as st

    _, run = st.spend_by_country(root, 16)
    total = sum(s.tasks for s in run)
    written = sum(s.bytes_out for s in run)
    cases = []
    for kept, detail in st.KEPT.items():
        cases.append(
            {
                "label": f"Kept {kept}",
                "detail": detail,
                "reference": {"label": "Tasks in the query", "value": total},
                "measured": st.rerun(run, 2, kept),
                "counters": [["bytes kept between stages", 0 if kept == "nowhere" else written]],
            }
        )
    return {
        "title": "A node fails in the third stage",
        "predict": {"label": "Tasks run again", "ask": "the tasks each runs again", "placeholder": "tasks"},
        "facts": (
            f"The query runs in {len(run)} stages on sixteen nodes: three of sixteen tasks each, and a "
            "sort of one. The node fails while the third stage runs."
        ),
        "cases": cases,
        "chart": {
            "x_label": "the stage the node fails in",
            "y_label": "tasks run again",
            "x_scale": "linear",
            "series": [
                {
                    "label": f"Kept {kept}",
                    "points": [[i + 1, st.rerun(run, i, kept)] for i in range(len(run))],
                }
                for kept in st.KEPT
            ],
        },
    }


#: Every measure panel, by the name a lab block gives it as ``of``.
def pushing(root: Path) -> dict:
    """ch18's two queries pushed and pulled, counting the bytes their scans read: a sink that wants
    one row, with a source that listens and one that does not, and two consumers of the returned
    orders, with a scan each and with one scan through a tee; then the bytes as consumers grow."""
    from .aggregate import Aggregate
    from .push import AVERAGE, TOTALS, any_returned, big_returners, big_returners_pulled

    def read(scans) -> int:
        return sum(s.metrics.bytes_read for s in scans)

    listening, _ = any_returned(root, listen=True)
    deaf, _ = any_returned(root, listen=False)
    pushed, groups = big_returners(root)
    pulled, _ = big_returners_pulled(root)
    whole = read(pushed)
    cases = [
        {
            "label": "Is there a returned order? The source listens",
            "detail": "scan → Exists",
            "reference": {"label": "Bytes read to the end", "value": deaf.metrics.bytes_read},
            "measured": listening.metrics.bytes_read,
            "counters": [
                ["row groups read", listening.metrics.batches_out],
                ["rows handed up", listening.metrics.rows_out],
            ],
        },
        {
            "label": "Is there a returned order? The source never listens",
            "detail": "scan → Exists",
            "reference": {"label": "Bytes read to the end", "value": deaf.metrics.bytes_read},
            "measured": deaf.metrics.bytes_read,
            "counters": [
                ["row groups read", deaf.metrics.batches_out],
                ["rows handed up", deaf.metrics.rows_out],
            ],
        },
        {
            "label": "Big returners, pulled: a scan for each consumer",
            "detail": "scan → totals; scan → average",
            "reference": {"label": "Bytes of one scan", "value": whole},
            "measured": read(pulled),
            "counters": [["scans", len(pulled)], ["rows handed up", sum(s.metrics.rows_out for s in pulled)]],
        },
        {
            "label": "Big returners, pushed: one scan through a tee",
            "detail": "scan → tee → totals, average",
            "reference": {"label": "Bytes of one scan", "value": whole},
            "measured": whole,
            "counters": [
                ["scans", len(pushed)],
                ["rows handed up", sum(s.metrics.rows_out for s in pushed)],
                ["rows each consumer took in", groups[0].metrics.rows_in],
            ],
        },
    ]
    sweep = [
        TOTALS,
        AVERAGE,
        (["customer_id"], [Aggregate("orders", "count")]),
        ([], [Aggregate("largest", "max", "amount")]),
    ]
    series = [
        {
            "label": label,
            "points": [[k, read(way(root, tuple(sweep[:k]))[0])] for k in range(1, len(sweep) + 1)],
        }
        for label, way in (("pulled, a scan each", big_returners_pulled), ("pushed, one scan", big_returners))
    ]
    return {
        "title": "Pushing the orders",
        "predict": {"label": "Bytes read", "ask": "the bytes each way reads", "placeholder": "bytes"},
        "facts": (
            "The sorted orders are ten row groups, and returned orders are spread through all of them. "
            "Each scan tests the status itself, reads the footer once, and then a row group at a time."
        ),
        "cases": cases,
        "chart": {
            "x_label": "consumers of the returned orders",
            "y_label": "bytes read",
            "x_scale": "linear",
            "series": series,
        },
    }


#: The operations the compiling panel's chart puts in the computed column.
OPERATION_SWEEP = (0, 1, 2, 4, 8)


def compiling(root: Path) -> dict:
    """ch01's returned orders over a unit price, run three ways over the sorted orders: interpreted
    a row at a time, interpreted a batch at a time, and compiled into one loop, counting the bytes
    each writes; then the bytes as the computed column takes more operations."""
    from .compile import Pipeline, compiled, interpreted, rows_at_a_time
    from .operators import Scan
    from .reference import read_query

    def run(pipeline, way):
        return way(
            pipeline, list(Scan(root / "fixtures" / "orders-sorted.parquet", pipeline.columns()).batches())
        )

    pipeline = Pipeline.of(read_query(root / "queries" / "returned_unit_price.sql"))
    cases = []
    for label, detail, way in (
        ("Interpreted, a row at a time", "ch06's evaluate_row", rows_at_a_time),
        ("Interpreted, a batch at a time", "ch06's evaluate, a kernel a node", interpreted),
        ("Compiled into one loop", "generate, then compile", compiled),
    ):
        r = run(pipeline, way)
        cases.append(
            {
                "label": label,
                "detail": detail,
                "reference": {"label": "Bytes of the result", "value": r.result.get_total_buffer_size()},
                "measured": r.written,
                "counters": [["nodes visited while running", r.dispatches], ["instructions", r.instructions]],
            }
        )
    series = []
    for label, way in (("a batch at a time", interpreted), ("compiled", compiled)):
        points = []
        for k in OPERATION_SWEEP:
            text = f"SELECT order_id, amount{' * 1.1' * k} AS price FROM 't' WHERE status = 'returned'"
            points.append([k, run(Pipeline.of(text), way).written])
        series.append({"label": label, "points": points})
    return {
        "title": "Three ways to run one pipeline",
        "predict": {"label": "Bytes written", "ask": "the bytes each way writes", "placeholder": "bytes"},
        "facts": (
            "The pipeline tests the status, then the unit price, and returns three columns of the orders "
            "that pass. A kernel writes an array for its result; a filter a batch of the rows it keeps. "
            "A value held in a variable is written nowhere."
        ),
        "cases": cases,
        "chart": {
            "x_label": "operations in the computed column",
            "y_label": "bytes written",
            "x_scale": "linear",
            "series": series,
        },
    }


MEASURES: dict[str, Callable[[Path], dict]] = {
    "aggregation": aggregation,
    "joins": joins,
    "sorting": sorting,
    "spilling": spilling,
    "planning": planning,
    "rules": rules,
    "join_orders": join_orders,
    "parallelism": parallelism,
    "shuffle": shuffle,
    "skew": skew,
    "stages": stages,
    "pushing": pushing,
    "compiling": compiling,
}
