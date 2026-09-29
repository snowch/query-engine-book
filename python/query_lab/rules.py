"""Rules that rewrite a logical plan into a cheaper one with the same answer (ch12).

Each rule is a function from a logical plan (:mod:`query_lab.planner`) to another, and each is
safe whatever the data: it never changes which rows come out, only the work of finding them. The
rules need nothing but the plan itself. None of them looks at a file's statistics or guesses a
size; choosing by size is ch13's.

- :func:`push_filters` splits each filter's condition into the parts joined by ``AND``, and moves
  each part as far down the plan as its columns allow: below a join to the side it reads, and
  into the scan when it compares a column with a constant.
- :func:`prune_columns` works out, from the top down, which columns each step needs, and has
  each table read only those.
- :func:`top_k` turns a sort with a limit above it into one step that keeps the first rows,
  ch09's top-k.
"""

from __future__ import annotations

from dataclasses import replace

from .expressions import Call, Column, Expression, Literal, nodes
from .operators import Comparison
from .planner import Compute, Get, Group, Join, Node, Order, Select, Take, Top, output

#: The comparisons a scan can test itself, and each one's mirror, for a constant on the left.
MIRRORED = {"=": "=", "!=": "!=", "<": ">", "<=": ">=", ">": "<", ">=": "<="}


def columns_in(expr: Expression) -> set[str]:
    """Every column an expression reads."""
    return {n.name for n in nodes(expr) if isinstance(n, Column)}


def conjuncts(condition: Expression) -> list[Expression]:
    """The parts of a condition joined by ``AND``: each must hold, so each can be tested alone."""
    if isinstance(condition, Call) and condition.op == "and":
        return [part for arg in condition.args for part in conjuncts(arg)]
    return [condition]


# Filters, pushed down. ---------------------------------------------------------------------------


def push_filters(node: Node) -> Node:
    """The plan with every filter's conditions moved as far down as their columns allow."""
    node = replace(node, children=[push_filters(c) for c in node.children])
    if not isinstance(node, Select):
        return node
    below = node.children[0]
    for part in conjuncts(node.condition):
        below = _push(below, part)
    return below


def _push(node: Node, condition: Expression) -> Node:
    """``node`` with ``condition`` tested as low inside it as its columns allow."""
    match node:
        case Join():
            for i, side in enumerate(node.children):
                if columns_in(condition) <= set(output(side)):
                    children = list(node.children)
                    children[i] = _push(side, condition)
                    return replace(node, children=children)
        case Get() if (comparison := _in_scan(condition, node)) is not None:
            return replace(node, filters=[*node.filters, comparison])
    return Select(children=[node], condition=condition)


def _in_scan(condition: Expression, get: Get) -> Comparison | None:
    """``condition`` as a comparison the scan can test itself, if it compares one column of the
    table with a constant; otherwise None, and a filter above the scan tests it."""
    if not (isinstance(condition, Call) and condition.op in MIRRORED):
        return None
    match condition.args:
        case (Column(name), Literal(value)):
            op = condition.op
        case (Literal(value), Column(name)):
            op = MIRRORED[condition.op]
        case _:
            return None
    prefix = f"{get.table.alias}." if get.qualified else ""
    return Comparison(name.removeprefix(prefix), op, value)


# Columns, pruned. -------------------------------------------------------------------------------


def prune_columns(node: Node, needed: set[str] | None = None) -> Node:
    """The plan with each table reading only the columns some step above it uses. ``needed`` is
    what the steps above ``node`` use of its output; at the top, all of it."""
    if needed is None:
        needed = set(output(node))
    match node:
        case Get(table=t, columns=columns, qualified=qualified):
            name = (lambda c: f"{t.alias}.{c}") if qualified else (lambda c: c)
            kept = [c for c in columns if name(c) in needed]
            # A step that counts rows needs no column, but a scan must read one to count them.
            return replace(node, columns=kept or columns[:1])
        case Compute(items=items):
            kept = [(n, e) for n, e in items if n in needed]
            below = set().union(*(columns_in(e) for _, e in kept))
            return replace(node, items=kept, children=[prune_columns(node.children[0], below)])
        case Select(condition=condition):
            below = needed | columns_in(condition)
        case Join(left_key=left, right_key=right):
            below = needed | {left, right}
            return replace(node, children=[prune_columns(c, below & set(output(c))) for c in node.children])
        case Group(keys=keys, aggregates=aggregates):
            below = set(keys) | {c for _, _, c in aggregates if c is not None}
        case Order(keys=keys) | Top(keys=keys):
            below = needed | {c for c, _ in keys}
        case _:
            below = needed
    return replace(node, children=[prune_columns(c, below) for c in node.children])


# A sort and a limit, as a top-k. ----------------------------------------------------------------


def top_k(node: Node) -> Node:
    """The plan with every limit directly above a sort turned into one top-k step."""
    node = replace(node, children=[top_k(c) for c in node.children])
    if isinstance(node, Take) and isinstance(node.children[0], Order):
        order = node.children[0]
        return Top(children=order.children, keys=order.keys, n=node.n)
    return node


#: The rules, in the order the book applies them.
RULES = (push_filters, prune_columns, top_k)
