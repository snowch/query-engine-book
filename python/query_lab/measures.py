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


#: Every measure panel, by the name a lab block gives it as ``of``.
MEASURES: dict[str, Callable[[Path], dict]] = {
    "aggregation": aggregation,
}
