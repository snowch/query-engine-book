"""Every generated fragment the chapters include: ``python -m query_lab figures``.

A chapter never types a number (CLAUDE.md, invariant 2). It includes a fragment from
``chapters/_generated/``, written here by running the engine or DuckDB on the fixtures. Every
fragment ends with a conditions line saying what computed it, on which fixture, with which
settings, so a reader can reproduce it.

``--check`` regenerates every fragment in memory and fails if a committed one differs: a change to
the engine, a fixture or DuckDB that moves a number fails the build until the fragments are
regenerated and committed.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import duckdb

from . import report
from .reference import Observation, observe, read_query

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "chapters" / "_generated"


@dataclass(frozen=True)
class Figure:
    name: str
    make: Callable[[], str]


def conditions(what: str, fixture: str) -> str:
    return f"\n*Computed by {what} on `fixtures/{fixture}`, at build time.*\n"


def duckdb_conditions(fixture: str) -> str:
    return conditions(f"DuckDB {duckdb.__version__} with one thread", fixture)


def plan_of(query: str, fixture: str) -> Callable[[], str]:
    def make() -> str:
        seen = observe(read_query(ROOT / "queries" / query))
        return f"```text\n{seen.plan.rstrip()}\n```\n" + duckdb_conditions(fixture)

    return make


def profile_table(seen: Observation) -> str:
    """The profile's counters beside the plan's estimates, one row per operator, top down."""
    rows = []
    for m, raw in zip(seen.metrics.walk(), _operators(seen.profile), strict=True):
        estimate = int(raw.get("extra_info", {}).get("Estimated Cardinality", 0))
        rows.append(f"| {m.operator} | {m.rows_in:,} | {estimate:,} | {m.rows_out:,} |")
    head = "| Operator | Rows in | Rows out, estimated | Rows out, measured |\n|---|---:|---:|---:|\n"
    return head + "\n".join(rows) + "\n"


def profile_of(query: str, fixture: str) -> Callable[[], str]:
    def make() -> str:
        return profile_table(observe(read_query(ROOT / "queries" / query))) + duckdb_conditions(fixture)

    return make


def _operators(profile: dict):
    node = profile["children"][0]
    while True:
        yield node
        if not node["children"]:
            return
        node = node["children"][0]


def orders_recipe() -> str:
    """How the orders were generated, from the generator's own constants and manifest."""
    sys.path.insert(0, str(ROOT / "fixtures"))
    import generate  # noqa: PLC0415

    m = json.loads((ROOT / "fixtures" / "orders-sorted.json").read_text())
    total = sum(w for _, w in generate.STATUSES)
    lines = [
        "| Column | How it was generated |",
        "|---|---|",
        f"| `order_id` | 1 to {m['rows']:,}, in order |",
        f"| `status` | {', '.join(f'{s} {w / total:.0%}' for s, w in generate.STATUSES)} |",
        "| `quantity` | a whole number from {} to {}, each equally likely |".format(*generate.QUANTITY),
        "| `amount` | `quantity` times a unit price drawn evenly between {:g} and {:g} |".format(
            *generate.UNIT_PRICE
        ),
    ]
    return "\n".join(lines) + "\n" + conditions("`fixtures/generate.py`", "orders-sorted.parquet")


def fixtures_table() -> str:
    """Every fixture, from the manifests the generator wrote."""
    lines = ["| File | Rows | Row groups | Bytes | Why it exists |", "|---|---:|---:|---:|---|"]
    for path in sorted((ROOT / "fixtures").glob("*.json")):
        m = json.loads(path.read_text())
        lines.append(
            f"| `{m['name']}.parquet` | {m['rows']:,} | {len(m['row_groups'])} | {m['file_bytes']:,} | {m['why']} |"
        )
    return (
        "\n".join(lines) + "\n" + "\n*Read from the manifests `fixtures/generate.py` wrote, at build time.*\n"
    )


FIGURES = (
    Figure("returned-unit-price-plan", plan_of("returned_unit_price.sql", "orders-sorted.parquet")),
    Figure("returned-unit-price-profile", profile_of("returned_unit_price.sql", "orders-sorted.parquet")),
    Figure("orders-recipe", orders_recipe),
    Figure("fixtures", fixtures_table),
)


#: Every panel a chapter embeds, as its ``lab`` block's settings. Each one's JSON is computed here
#: at build time, embedded in the page by the renderer, and recomputed in the page on request.
PANELS = ({"experiment": "plan", "query": "returned_unit_price.sql"},)


def panel_json(config: dict[str, str]) -> str:
    return json.dumps(report.run(ROOT, config), indent=1) + "\n"


def outputs() -> dict[str, Callable[[], str]]:
    """Every generated file, by name: the fragments, then the panels' JSON."""
    out: dict[str, Callable[[], str]] = {f"{f.name}.md": f.make for f in FIGURES}
    for config in PANELS:
        out[report.panel_name(config)] = lambda config=config: panel_json(config)
    return out


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale = []
    OUT.mkdir(parents=True, exist_ok=True)
    made = outputs()
    for name, make in made.items():
        path = OUT / name
        text = make()
        if check:
            if not path.exists() or path.read_text() != text:
                stale.append(path.name)
        else:
            path.write_text(text)
    orphans = sorted(p.name for p in OUT.glob("*") if p.is_file() and p.name not in made)
    if check:
        if stale or orphans:
            print("stale generated fragments (run `make figures` and commit):", ", ".join(stale + orphans))
            return 1
        print(f"  {len(made)} generated fragments and panels are current")
        return 0
    for name in orphans:
        (OUT / name).unlink()
    print(f"wrote {len(made)} fragments and panels to {OUT.relative_to(ROOT)}")
    return 0
