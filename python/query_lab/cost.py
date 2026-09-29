"""Estimates, cost and the order of joins (ch13).

ch12's rules never needed to know how big anything was. Choosing the order of joins does: the
same rows come out of every order, and the work in between differs by orders of magnitude. The
planner cannot run each order to find out, so it estimates, from what the files' footers say.

- :func:`table_stats` reads a file's footer: its rows, and each column's smallest and largest
  value and count of nulls. For whole numbers and dates it bounds the distinct values by the
  range; for anything else the footer says nothing about them.
- :func:`selectivity` guesses the fraction of rows a condition keeps: values spread evenly
  between the smallest and the largest, conditions independent of each other, and a fixed guess
  where the statistics say nothing.
- :func:`estimate` carries those guesses up the plan, step by step, to the rows each step hands up.
- :func:`join_order` is a rule that tries every order of a query's joins and keeps the one whose
  joins hand up the fewest rows in total, with the smaller input of each join as its build side.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
from functools import cache
from itertools import combinations
from pathlib import Path

import pyarrow.parquet as pq

from .expressions import Call, Column, Expression, Literal
from .operators import Comparison
from .planner import Get, Group, Join, Node, Select, Take, Top, output

#: The fraction of rows a condition is guessed to keep when the statistics cannot say: DuckDB's.
GUESS = 0.2


@dataclass(frozen=True)
class ColumnStats:
    low: object
    high: object
    nulls: int
    distinct: int | None
    """At most this many distinct values, if the footer's range lets the planner say; else None."""
    rows: int
    """The table's rows: at most this many distinct values, whatever the column holds."""

    @property
    def bound(self) -> int:
        """The most distinct values the column can hold, by what the footer says."""
        return self.distinct if self.distinct is not None else self.rows


@dataclass(frozen=True)
class TableStats:
    rows: int
    columns: dict[str, ColumnStats]


@cache
def table_stats(path: Path) -> TableStats:
    """What a file's footer says about its rows: no data page is read."""
    md = pq.ParquetFile(path).metadata
    columns = {}
    for c in range(md.num_columns):
        chunks = [md.row_group(g).column(c) for g in range(md.num_row_groups)]
        found = [s for s in (ch.statistics for ch in chunks) if s is not None and s.has_min_max]
        low = min(s.min for s in found) if found else None
        high = max(s.max for s in found) if found else None
        distinct = None
        if isinstance(low, int | dt.date) and not isinstance(low, bool):
            span = (high - low).days if isinstance(low, dt.date) else high - low
            distinct = min(md.num_rows, span + 1)
        nulls = sum(s.null_count for s in found)
        columns[chunks[0].path_in_schema] = ColumnStats(low, high, nulls, distinct, md.num_rows)
    return TableStats(md.num_rows, columns)


def _fraction(stats: ColumnStats, op: str, value: object) -> float:
    """The fraction of a column's values a comparison with a constant keeps, if they are spread
    evenly between the smallest and the largest."""
    if op in ("=", "!="):
        equal = 1 / stats.distinct if stats.distinct else GUESS
        if stats.low is not None and not stats.low <= value <= stats.high:
            equal = 0.0
        return equal if op == "=" else 1 - equal
    try:
        width = _minus(stats.high, stats.low)
        below = min(max(_minus(value, stats.low) / width, 0.0), 1.0) if width else 0.5
    except TypeError:
        return GUESS
    # A strict comparison and its inclusive twin differ by one value: too little to estimate.
    return below if op in ("<", "<=") else 1 - below


def _minus(a, b) -> float:
    return (a - b).days if isinstance(a, dt.date) else float(a - b)


def selectivity(condition: Expression | Comparison, columns: dict[str, ColumnStats]) -> float:
    """The fraction of rows ``condition`` is guessed to keep, from the stats of the columns it
    reads, by the names the plan uses. Conditions joined by AND are guessed independent."""
    match condition:
        case Comparison(column=name, op=op, value=value) if name in columns:
            return _fraction(columns[name], op, value)
        case Call("and", (a, b)):
            return selectivity(a, columns) * selectivity(b, columns)
        case Call("or", (a, b)):
            x, y = selectivity(a, columns), selectivity(b, columns)
            return x + y - x * y
        case Call("not", (a,)):
            return 1 - selectivity(a, columns)
        case Call(op, (Column(name), Literal(value))) if name in columns and op in _OPS:
            return _fraction(columns[name], op, value)
        case Call(op, (Literal(value), Column(name))) if name in columns and op in _OPS:
            return _fraction(columns[name], _OPS[op], value)
    return GUESS


_OPS = {"=": "=", "!=": "!=", "<": ">", "<=": ">=", ">": "<", ">=": "<="}


def column_stats(root: Path, node: Node) -> dict[str, ColumnStats]:
    """The stats of every column the tables below ``node`` read, by the names the plan uses."""
    out = {}
    for get in (n for n in node.walk() if isinstance(n, Get)):
        prefix = f"{get.table.alias}." if get.qualified else ""
        for name, s in table_stats(root / get.table.path).columns.items():
            out[prefix + name] = s
    return out


def estimate(root: Path, node: Node) -> float:
    """The rows ``node`` is guessed to hand up, from the files' footers alone."""
    match node:
        case Get(table=t, filters=filters):
            stats = table_stats(root / t.path)
            rows = float(stats.rows)
            for f in filters:
                rows *= selectivity(f, stats.columns)
            return rows
        case Select(condition=condition):
            return estimate(root, node.children[0]) * selectivity(condition, column_stats(root, node))
        case Join(left_key=left, right_key=right):
            sides = [estimate(root, c) for c in node.children]
            stats = column_stats(root, node)
            # The footer gives only a bound on each key's distinct values, and the smaller bound is
            # the tighter: the planner takes it as the distinct keys on both sides, each matching.
            return sides[0] * sides[1] / min(stats[left].bound, stats[right].bound)
        case Group(keys=keys):
            below = estimate(root, node.children[0])
            stats = column_stats(root, node)
            groups = 1.0
            for k in keys:
                groups *= stats[k].distinct if k in stats and stats[k].distinct else below
            return min(below, groups)
        case Take(n=n) | Top(n=n):
            return min(float(n), estimate(root, node.children[0]))
    return estimate(root, node.children[0])


def joined_rows(root: Path, node: Node) -> float:
    """The cost of a plan: the rows every join in it is guessed to hand up, added together."""
    own = estimate(root, node) if isinstance(node, Join) else 0.0
    return own + sum(joined_rows(root, c) for c in node.children)


# The order of joins. ----------------------------------------------------------------------------


def join_order(root: Path, node: Node) -> Node:
    """The plan with each tree of joins rebuilt in the order whose joins hand up the fewest rows,
    by estimate, and the smaller input of each join as its build side."""
    if not isinstance(node, Join):
        return replace(node, children=[join_order(root, c) for c in node.children])
    leaves, keys = _flatten(node)
    leaves = [join_order(root, leaf) for leaf in leaves]
    best: dict[frozenset, tuple[float, Node]] = {frozenset([i]): (0.0, leaf) for i, leaf in enumerate(leaves)}
    for size in range(2, len(leaves) + 1):
        for chosen in map(frozenset, combinations(range(len(leaves)), size)):
            for k in range(1, size):
                for part in map(frozenset, combinations(sorted(chosen), k)):
                    rest = chosen - part
                    if part not in best or rest not in best or min(part) > min(rest):
                        continue
                    joined = _join(root, best[part][1], best[rest][1], keys)
                    if joined is None:
                        continue
                    total = best[part][0] + best[rest][0] + estimate(root, joined)
                    if chosen not in best or total < best[chosen][0]:
                        best[chosen] = (total, joined)
    return best[frozenset(range(len(leaves)))][1]


def _flatten(node: Node) -> tuple[list[Node], list[tuple[str, str]]]:
    """The inputs of a tree of joins, and the pairs of keys it joins them on."""
    if not isinstance(node, Join):
        return [node], []
    leaves, keys = [], [(node.left_key, node.right_key)]
    for child in node.children:
        more, pairs = _flatten(child)
        leaves += more
        keys += pairs
    return leaves, keys


def _join(root: Path, a: Node, b: Node, keys: list[tuple[str, str]]) -> Join | None:
    """A join of ``a`` and ``b`` on a pair of keys one side each holds, built on the smaller of
    the two, or None if no pair of keys links them."""
    ours, theirs = set(output(a)), set(output(b))
    for left, right in keys:
        for x, y in ((left, right), (right, left)):
            if x in ours and y in theirs:
                probe, build, pk, bk = (
                    (a, b, x, y) if estimate(root, a) >= estimate(root, b) else (b, a, y, x)
                )
                return Join(children=[probe, build], left_key=pk, right_key=bk)
    return None
