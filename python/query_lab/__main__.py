"""The engine's command line.

    python3 -m query_lab observe queries/returned_unit_price.sql   # DuckDB's plan and profile
    python3 -m query_lab figures [--check]                         # the chapters' fragments
    python3 -m query_lab report plan returned_unit_price.sql [--sql TEXT]
                                                                   # a panel's JSON, as the page gets it

Run from the repository's root, with ``PYTHONPATH=python``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import figures, report
from .reference import observe, read_query

USAGE = (
    "usage: python3 -m query_lab observe <query.sql> | figures [--check]"
    " | report <experiment> <query.sql> [--sql TEXT]"
)


def main(argv: list[str]) -> int:
    match argv:
        case ["figures", *rest]:
            return figures.main(rest)
        case ["observe", path]:
            seen = observe(read_query(path))
            print(seen.plan.rstrip())
            print()
            print(figures.profile_table(seen), end="")
            print(f"\n{len(seen.rows)} rows")
            return 0
        case ["report", experiment, query, *rest]:
            config = {"experiment": experiment, "query": query}
            match rest:
                case []:
                    pass
                case ["--sql", sql]:
                    config["sql"] = sql
                case _:
                    print(USAGE, file=sys.stderr)
                    return 2
            print(json.dumps(report.run(Path.cwd(), config), separators=(",", ":")))
            return 0
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
