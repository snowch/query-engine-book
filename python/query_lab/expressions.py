"""Expressions: a tree of columns, constants and operators, evaluated a batch at a time (ch06).

A query's ``WHERE`` and ``SELECT`` are expressions. An engine parses each into a tree whose
leaves are columns and constants and whose inner nodes are operators, then evaluates the tree.
It can do that a row at a time, visiting every node for every row, or a batch at a time,
visiting every node once per batch and running each operator over a whole array with one
**kernel**: a loop, compiled ahead of time, that applies one operator to every value.

The evaluator counts, it does not time: how many nodes it visited (``dispatches``). At each
visit it decides what to run: once per row a row at a time, once per batch a batch at a time. Given a vector unit from
:mod:`query_lab.cpu`, it also counts the instructions its operators would run. COUNTERS.md, *The
simulators' counters*, defines both.
"""

from __future__ import annotations

import operator
from collections.abc import Iterator
from dataclasses import dataclass

import pyarrow as pa
import pyarrow.compute as pc

from .cpu import VectorUnit

# An expression is a tree of three kinds of node. Frozen, so a tree can be shared and compared.


@dataclass(frozen=True)
class Column:
    """A column of the batch, by name."""

    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Literal:
    """A constant, the same for every row."""

    value: object

    def __str__(self) -> str:
        return repr(self.value)


@dataclass(frozen=True)
class Call:
    """An operator applied to the values of its arguments, each an expression itself."""

    op: str
    args: tuple[Expression, ...]

    def __str__(self) -> str:
        if len(self.args) == 2:
            return f"({self.args[0]} {self.op} {self.args[1]})"
        return f"{self.op}({', '.join(map(str, self.args))})"


Expression = Column | Literal | Call


def _divide(a, b):
    # Division is always floating point, as in DuckDB: 20 / 100 is 0.2, not nought.
    return pc.divide(pc.cast(a, pa.float64()), pc.cast(b, pa.float64()))


#: The kernel for each operator: one call applies it to every value of whole arrays.
KERNELS = {
    "+": pc.add,
    "-": pc.subtract,
    "*": pc.multiply,
    "/": _divide,
    "=": pc.equal,
    "!=": pc.not_equal,
    "<": pc.less,
    "<=": pc.less_equal,
    ">": pc.greater,
    ">=": pc.greater_equal,
    "and": pc.and_kleene,
    "or": pc.or_kleene,
    "not": pc.invert,
    "lower": pc.utf8_lower,
}

#: The same operators, applied to one value at a time. Division borrows the kernel's, so that
#: dividing by nought gives infinity, as it does for a whole array, rather than an exception.
SCALARS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": lambda a, b: _divide(pa.scalar(float(a)), pa.scalar(float(b))).as_py(),
    "=": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
    "not": operator.not_,
    "lower": str.lower,
}


@dataclass
class Counts:
    """What evaluating an expression cost the evaluator."""

    dispatches: int = 0
    """Nodes visited: each one a decision about what to run, made before any value is computed."""


def evaluate(
    expr: Expression, batch: pa.RecordBatch, counts: Counts | None = None, unit: VectorUnit | None = None
):
    """The expression's value for every row of ``batch``, a batch at a time: each node is visited
    once, and each operator runs as one kernel over the whole batch."""
    if counts is not None:
        counts.dispatches += 1
    match expr:
        case Column(name):
            return batch.column(name)
        case Literal(value):
            return pa.scalar(value)
        case Call(op, args):
            values = [evaluate(a, batch, counts, unit) for a in args]
            if unit is not None:
                unit.run(batch.num_rows)
            return KERNELS[op](*values)
    raise TypeError(f"not an expression: {expr!r}")


def evaluate_row(expr: Expression, row: dict, counts: Counts | None = None, unit: VectorUnit | None = None):
    """The expression's value for one row, given as a dict of the row's columns: each node is
    visited once for this row alone."""
    if counts is not None:
        counts.dispatches += 1
    match expr:
        case Column(name):
            return row[name]
        case Literal(value):
            return value
        case Call(op, args):
            values = [evaluate_row(a, row, counts, unit) for a in args]
            if unit is not None:
                unit.run(1)
            return SCALARS[op](*values)
    raise TypeError(f"not an expression: {expr!r}")


def nodes(expr: Expression) -> Iterator[Expression]:
    """Every node of the tree, the root first."""
    yield expr
    if isinstance(expr, Call):
        for a in expr.args:
            yield from nodes(a)


def batches_of(table: pa.Table, size: int) -> Iterator[pa.RecordBatch]:
    """The table cut into batches of ``size`` rows, the last one shorter, whatever batches it was
    built from."""
    yield from table.combine_chunks().to_batches(max_chunksize=size)
