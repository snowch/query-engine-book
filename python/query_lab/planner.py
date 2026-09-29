"""From a syntax tree to a plan the engine can run (ch11).

The parser (:mod:`query_lab.sql`) says what a query wrote. The planner decides what to run, in
three steps.

**Binding** checks every name against the tables the query reads: which table each column
belongs to, and that it exists. A column two tables both have must be qualified, ``o.customer_id``.

**The logical plan** is the query's meaning as a tree of relational steps, each a :class:`Node`:
read a table, keep the rows a condition holds for, join, group, compute, sort, limit. It says
what each step hands up, not how. The planner builds it the plain way, in the order SQL defines a
query's meaning: read every column of every table, join them as written, filter, group, compute
the ``SELECT`` list, sort, limit.

**The physical plan** is the engine's operators, one for each logical step. Nothing here chooses
between ways of doing a step: ch12's rules rewrite the logical plan first, and ch13 chooses by
cost.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

import pyarrow.parquet as pq

from .aggregate import Aggregate, HashAggregate
from .expressions import Call, Column, Expression, evaluate
from .join import HashJoin
from .operators import Comparison, Filter, Operator, Project, Scan
from .sort import Sort, TopK
from .sql import Query, Table, parse

#: The aggregate functions the planner knows.
AGGREGATES = ("count", "sum", "min", "max", "avg")


class PlanError(ValueError):
    """A query the planner cannot bind or cannot run: it says which name, or which feature."""


# The logical plan's steps. -----------------------------------------------------------------------


@dataclass
class Node:
    """A step of a logical plan: what it hands up, from what its children hand up."""

    children: list[Node] = field(default_factory=list)

    def walk(self) -> Iterator[Node]:
        yield self
        for c in self.children:
            yield from c.walk()


@dataclass
class Get(Node):
    """Read ``columns`` of a table, and only the rows ``filters`` keep (ch12 pushes them here)."""

    table: Table = None
    columns: list[str] = field(default_factory=list)
    filters: list[Comparison] = field(default_factory=list)
    qualified: bool = False
    """Whether the plan names the columns ``alias.column``, as it does when the query joins."""

    def __str__(self) -> str:
        s = f"Get {self.table.path}: {', '.join(self.columns)}"
        return s + (f"; {' AND '.join(map(str, self.filters))}" if self.filters else "")


@dataclass
class Select(Node):
    """Keep the rows ``condition`` is true for."""

    condition: Expression = None

    def __str__(self) -> str:
        return f"Filter {self.condition}"


@dataclass
class Join(Node):
    """Pair the left child's rows with the right's where ``left_key`` equals ``right_key``."""

    left_key: str = ""
    right_key: str = ""

    def __str__(self) -> str:
        return f"Join {self.left_key} = {self.right_key}"


@dataclass
class Group(Node):
    """Group by ``keys``, columns of the child, and compute ``aggregates``: each a name, a
    function, and the column it takes, or None for ``count(*)``."""

    keys: list[str] = field(default_factory=list)
    aggregates: list[tuple[str, str, str | None]] = field(default_factory=list)

    def __str__(self) -> str:
        aggs = ", ".join(f"{f}({c or '*'})" for _, f, c in self.aggregates)
        return f"Aggregate by {', '.join(self.keys) or 'nothing'}: {aggs}"


@dataclass
class Compute(Node):
    """Hand up ``items``, each a name and the expression that computes it."""

    items: list[tuple[str, Expression]] = field(default_factory=list)

    def __str__(self) -> str:
        return "Project " + ", ".join(n if str(e) == n else f"{e} AS {n}" for n, e in self.items)


@dataclass
class Order(Node):
    """Sort by ``keys``, each a column and whether it is descending."""

    keys: list[tuple[str, bool]] = field(default_factory=list)

    def __str__(self) -> str:
        return "Sort " + ", ".join(f"{c} {'DESC' if d else 'ASC'}" for c, d in self.keys)


@dataclass
class Take(Node):
    """Hand up the first ``n`` rows."""

    n: int = 0

    def __str__(self) -> str:
        return f"Limit {self.n}"


@dataclass
class Top(Node):
    """Hand up the first ``n`` rows in the order of ``keys``: a sort and a limit as one step (ch12)."""

    keys: list[tuple[str, bool]] = field(default_factory=list)
    n: int = 0

    def __str__(self) -> str:
        return f"Top {self.n} by " + ", ".join(f"{c} {'DESC' if d else 'ASC'}" for c, d in self.keys)


def show(node: Node, depth: int = 0) -> str:
    """The logical plan as indented lines, the root first."""
    return "\n".join(["  " * depth + str(node), *(show(c, depth + 1) for c in node.children)])


# Binding. ----------------------------------------------------------------------------------------


@dataclass
class Scope:
    """The tables a query reads, by the names the query gives them, and each one's columns."""

    columns: dict[str, list[str]]
    joined: bool

    def resolve(self, name: str) -> str:
        """A column as the query wrote it, as the plan names it: plain for a query of one table,
        ``alias.column`` for a join, where two tables may share a name."""
        alias, _, column = name.rpartition(".")
        if alias and alias not in self.columns:
            raise PlanError(f"no table is called {alias!r}")
        owners = [alias] if alias else [a for a, cs in self.columns.items() if column in cs]
        if not owners or column not in self.columns[owners[0]]:
            raise PlanError(f"no table has a column {name!r}")
        if len(owners) > 1:
            raise PlanError(f"{column!r} is in {' and '.join(owners)}: say which, as {owners[0]}.{column}")
        return f"{owners[0]}.{column}" if self.joined else column

    def bind(self, expr: Expression) -> Expression:
        """``expr`` with every column resolved."""
        match expr:
            case Column(name):
                return Column(self.resolve(name))
            case Call(op, args):
                return Call(op, tuple(self.bind(a) for a in args))
        return expr


def columns_of(root: Path, table: Table) -> list[str]:
    """The columns of a table the query reads, from its file's footer."""
    if table.options or any(ch in table.path for ch in "*?["):
        raise PlanError(f"your planner reads one plain Parquet file, not {table.path} with options")
    if not (root / table.path).is_file():
        raise PlanError(f"no file {table.path}")
    return pq.read_schema(root / table.path).names


# The logical plan, the plain way. ----------------------------------------------------------------


def logical_plan(root: Path, query: Query) -> Node:
    """The query's meaning as a logical plan, built in the order SQL defines it."""
    tables = [query.table, *(j.table for j in query.joins)]
    scope = Scope({t.alias: columns_of(root, t) for t in tables}, joined=bool(query.joins))
    if len(scope.columns) != len(tables):
        raise PlanError("two tables have the same name: give each its own alias")
    gets = [Get(table=t, columns=scope.columns[t.alias], qualified=scope.joined) for t in tables]

    plan: Node = gets[0]
    for join, get in zip(query.joins, gets[1:], strict=True):
        on = scope.bind(join.on)
        if not (isinstance(on, Call) and on.op == "=" and all(isinstance(a, Column) for a in on.args)):
            raise PlanError(f"your planner joins on one column equal to another, not {join.on}")
        left, right = (a.name for a in on.args)
        if left.startswith(f"{join.table.alias}."):
            left, right = right, left
        plan = Join(children=[plan, get], left_key=left, right_key=right)
    if query.where is not None:
        plan = Select(children=[plan], condition=scope.bind(query.where))

    if query.star:
        items = [(c, Column(c)) for g in gets for c in output(g)]
    else:
        items = [(item.alias or name_of(item.expr), scope.bind(item.expr)) for item in query.items]
    if query.group_by or any(_aggregate(e) for _, e in items):
        plan, items = _grouped(plan, [scope.bind(e) for e in query.group_by], items)
    plan = Compute(children=[plan], items=items)

    if query.order_by:
        names = {n for n, _ in items}
        keys = []
        for e, descending in query.order_by:
            if not (isinstance(e, Column) and e.name in names):
                raise PlanError(f"your planner sorts by a column the query hands up, not {e}")
            keys.append((e.name, descending))
        plan = Order(children=[plan], keys=keys)
    if query.limit is not None:
        plan = Take(children=[plan], n=query.limit)
    return plan


def _grouped(plan: Node, keys: list[Expression], items: list[tuple[str, Expression]]):
    """A Group over ``plan``, with a Compute below it for any key or argument that is not a
    column, and the ``SELECT`` list rewritten to read the group's columns."""
    needed = {str(k): k for k in keys}
    aggregates = []
    for name, e in items:
        if _aggregate(e):
            argument = e.args[0] if e.args else None
            if argument is not None:
                needed[str(argument)] = argument
            aggregates.append((name, e.op, None if argument is None else str(argument)))
    if any(not isinstance(e, Column) or e.name != n for n, e in needed.items()):
        plan = Compute(children=[plan], items=list(needed.items()))
    group = Group(children=[plan], keys=[str(k) for k in keys], aggregates=aggregates)
    return group, [(n, Column(n) if _aggregate(e) else _over_keys(e, set(group.keys))) for n, e in items]


def _aggregate(e: Expression) -> bool:
    """Whether ``e`` is an aggregate: one call of an aggregate function, over no aggregate."""
    inner = [a for a in e.args if _aggregate(a)] if isinstance(e, Call) else []
    if isinstance(e, Call) and e.op in AGGREGATES:
        if inner:
            raise PlanError(f"an aggregate inside an aggregate: {e}")
        return True
    if inner:
        raise PlanError(f"your planner hands up an aggregate alone, not inside {e}")
    return False


def _over_keys(e: Expression, keys: set[str]) -> Expression:
    """An item of the ``SELECT`` list over the group's keys, as columns of the group's output."""
    if str(e) in keys:
        return Column(str(e))
    if isinstance(e, Call):
        return Call(e.op, tuple(_over_keys(a, keys) for a in e.args))
    if isinstance(e, Column):
        raise PlanError(f"{e.name} is neither grouped by nor aggregated")
    return e


def name_of(e: Expression) -> str:
    """The name an item of the ``SELECT`` list is handed up under when the query gives none: a
    column's own name, and otherwise the expression's text."""
    if isinstance(e, Column):
        return e.name.rpartition(".")[2]
    return "count_star()" if isinstance(e, Call) and e.op == "count" and not e.args else str(e)


def output(node: Node) -> list[str]:
    """The columns a logical step hands up, by the names the plan uses."""
    match node:
        case Get(table=t, columns=columns, qualified=qualified):
            return [f"{t.alias}.{c}" for c in columns] if qualified else list(columns)
        case Join():
            return [*output(node.children[0]), *output(node.children[1])]
        case Group(keys=keys, aggregates=aggregates):
            return [*keys, *(n for n, _, _ in aggregates)]
        case Compute(items=items):
            return [n for n, _ in items]
    return output(node.children[0])


# The physical plan. ------------------------------------------------------------------------------


def physical_plan(root: Path, node: Node) -> Operator:
    """The engine's operators for a logical plan: one for each step."""
    kids = [physical_plan(root, c) for c in node.children]
    match node:
        case Get(table=t, columns=columns, filters=filters, qualified=qualified):
            scan = Scan(root / t.path, columns, filters=filters)
            if not qualified:
                return scan
            # Two joined tables may share a column's name: each is renamed for its table.
            return Project(scan, {f"{t.alias}.{c}": partial(evaluate, Column(c)) for c in columns})
        case Select(condition=condition):
            return Filter(kids[0], str(condition), partial(evaluate, condition))
        case Join(left_key=left, right_key=right):
            columns = [("probe", c) for c in output(node.children[0])]
            columns += [("build", c) for c in output(node.children[1])]
            return HashJoin(kids[0], kids[1], left, right, columns)
        case Group(keys=keys, aggregates=aggregates):
            return HashAggregate(kids[0], keys, [Aggregate(n, f, c) for n, f, c in aggregates])
        case Compute(items=items):
            return Project(kids[0], {n: partial(evaluate, e) for n, e in items})
        case Order(keys=keys):
            return Sort(kids[0], keys)
        case Take(n=n):
            # The first rows as they come: ch09's top-k, with nothing to order them by.
            return TopK(kids[0], [], n)
        case Top(keys=keys, n=n):
            return TopK(kids[0], keys, n)
    raise PlanError(f"no operator for {node}")


def plan(root: Path, text: str, rules: tuple = ()) -> Operator:
    """The engine's operators for a query's text: parsed, bound, planned the plain way, then
    rewritten by each of ``rules`` in turn (ch12's :mod:`query_lab.rules`)."""
    logical = logical_plan(root, parse(text))
    for rule in rules:
        logical = rule(logical)
    return physical_plan(root, logical)
