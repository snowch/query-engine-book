"""What the desk and the browser must agree on, as one JSON document.

    python3 spikes/duckdb-pyodide/probe.py          # at a desk, from the repository's root
    node spikes/duckdb-pyodide/node.mjs             # the same file, under Pyodide in Node
    node spikes/duckdb-pyodide/browser.mjs          # the same file, under Pyodide in Chromium

For every query in ``queries/``: DuckDB's result, its ``EXPLAIN`` plan, and the counters from its
JSON profile. Then the Parquet book's scan, the book's scan layer, on both orders fixtures. Then
the book's engine: every hand-written plan's result and counters, which exercise the Parquet
book's reader and pyarrow's kernels as the page runs them. The
three runs must print the same document, byte for byte; ``tests/test_pyodide.py`` checks the
desk against Node, and ``scripts/ci-check.sh`` runs the browser.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Run from the repository's root, as a desk and the page both do: the engine and the scan layer
# are imported from where the repository keeps them.
ROOT = Path.cwd()
for extra in ("python", "external/parquet-book/python"):
    sys.path.insert(0, str(ROOT / extra))

import duckdb  # noqa: E402
from parquet_lab.object_store import NetworkModel  # noqa: E402
from parquet_lab.prune import Op  # noqa: E402
from parquet_lab.scan import Query, Strategy, scan  # noqa: E402

from query_lab.plans import PLANS, plan_for  # noqa: E402
from query_lab.reference import observe, read_query  # noqa: E402


def probe(root: Path) -> dict:
    out: dict = {"duckdb": duckdb.__version__, "queries": {}, "scans": {}}
    for path in sorted((root / "queries").glob("*.sql")):
        seen = observe(read_query(path))
        out["queries"][path.name] = {
            "columns": seen.columns,
            "rows": [list(r) for r in seen.rows],
            "plan": seen.plan,
            "operators": [[m.operator, m.rows_in, m.rows_out] for m in seen.metrics.walk()],
        }
    for name in ("orders-sorted", "orders-shuffled"):
        data = (root / "fixtures" / f"{name}.parquet").read_bytes()
        result = scan(data, name, Query(columns=[0], condition=(0, Op.LT, "500")), Strategy(), NetworkModel())
        out["scans"][name] = {
            "matches": len(result.matches),
            "rows_decoded": result.rows_decoded,
            "bytes_fetched": result.bytes_fetched,
            "requests": len(result.requests),
        }
    out["engine"] = {}
    for query in sorted(PLANS):
        plan = plan_for(root, query)
        table = plan.run()
        out["engine"][query] = {"rows": table.to_pylist(), "metrics": plan.metrics.to_json()}
    return out


if __name__ == "__main__":
    print(json.dumps(probe(ROOT), sort_keys=True))
