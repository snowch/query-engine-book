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


#: Every measure panel, by the name a lab block gives it as ``of``.
MEASURES: dict[str, Callable[[Path], dict]] = {
    "aggregation": aggregation,
    "joins": joins,
    "sorting": sorting,
    "spilling": spilling,
}
