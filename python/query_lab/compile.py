"""Compiling a query: a pipeline turned into one loop of Python, written from its trees (ch19).

The engine so far interprets. For every batch, each operator walks its expression trees, and each
node of a tree runs one kernel over the whole batch and writes its result to a new array, for the
node above it to read (ch06). A compiling engine walks the trees once, before it reads a row, and
writes code: one loop over the rows that tests every filter and computes every output column, with
each value kept in a local variable from the moment it is computed to the moment it is used. The
code is compiled, here by Python's own ``compile``, and the function it defines runs once a batch.

The module counts what compiling saves the interpreter: the nodes it visits as it runs (none; the
compiler visited each once) and the bytes it writes to arrays between kernels (none but the
result's). It counts, too, what the loop gives up: each operation runs on one value at a time, so
it takes an instruction for every value, where a kernel took one for every lane-full
(:mod:`query_lab.cpu`).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import pyarrow as pa

from .cpu import VectorUnit
from .expressions import KERNELS, Call, Column, Counts, Expression, Literal, _divide, evaluate_row, nodes
from .planner import name_of
from .rules import conjuncts
from .sql import parse

#: The Python for each operator, applied to one value at a time.
PYTHON = {
    "+": "({} + {})",
    "-": "({} - {})",
    "*": "({} * {})",
    "/": "divide({}, {})",
    "=": "({} == {})",
    "!=": "({} != {})",
    "<": "({} < {})",
    "<=": "({} <= {})",
    ">": "({} > {})",
    ">=": "({} >= {})",
    "and": "({} and {})",
    "or": "({} or {})",
    "not": "(not {})",
    "lower": "{}.lower()",
}


def divide(a, b) -> float:
    """Division as the kernels do it: always floating point, and by nought to infinity."""
    return float(a) / b if b else _divide(pa.scalar(float(a)), pa.scalar(float(b))).as_py()


@dataclass(frozen=True)
class Pipeline:
    """What a query of one table asks of each row: the filters it must pass, in order, and the
    columns to compute from it."""

    filters: tuple[Expression, ...]
    outputs: tuple[tuple[str, Expression], ...]

    @staticmethod
    def of(text: str) -> Pipeline:
        """The pipeline of a query's text, from ch11's parser: its ``WHERE``, split at each ``AND``,
        and its ``SELECT`` list."""
        query = parse(text)
        filters = conjuncts(query.where) if query.where is not None else []
        return Pipeline(tuple(filters), tuple((i.alias or name_of(i.expr), i.expr) for i in query.items))

    def columns(self) -> list[str]:
        """The input columns the pipeline reads."""
        trees = [*self.filters, *(e for _, e in self.outputs)]
        return sorted({n.name for t in trees for n in nodes(t) if isinstance(n, Column)})


def python(expr: Expression, shared: dict[Expression, str] | None = None) -> str:
    """Python for ``expr``'s value in row ``i``: each column indexed by ``i``, each operator written
    out, and each value in ``shared`` read from the local variable that holds it."""
    if shared and expr in shared:
        return shared[expr]
    match expr:
        case Column(name):
            return f"{name}[i]"
        case Literal(value):
            return repr(value)
        case Call(op, args):
            return PYTHON[op].format(*(python(a, shared) for a in args))
    raise TypeError(f"not an expression: {expr!r}")


@dataclass
class Generated:
    """The code the compiler wrote for a pipeline, and what writing it cost."""

    source: str
    nodes: int
    """Nodes of the trees the compiler visited: each once, before any row is read."""


def generate(pipeline: Pipeline, counting: bool = False) -> Generated:
    """The source of one function that runs ``pipeline`` on a batch, a row at a time.

    Each filter skips the row as soon as it fails, so a later filter's values are computed only
    for the rows that got that far. A value the trees use more than once is computed once, into a
    local variable, the first time a tree needs it.
    """
    trees = [*pipeline.filters, *(e for _, e in pipeline.outputs)]
    uses = Counter(n for t in trees for n in nodes(t) if isinstance(n, Call))
    shared: dict[Expression, str] = {}
    lines: list[str] = []

    def line(text: str, expr: Expression) -> None:
        """One line of the loop's body. Counting, it first counts the operations the line runs."""
        if counting:
            lines.append(f"        count({_operations(expr, shared)})")
        lines.append(f"        {text}")

    def share(expr: Expression) -> None:
        """Compute each value ``expr`` shares with another tree into a variable, innermost first."""
        for a in expr.args if isinstance(expr, Call) else ():
            share(a)
        if uses[expr] > 1 and expr not in shared:
            name = f"v{len(shared)}"
            line(f"{name} = {python(expr, shared)}", expr)
            shared[expr] = name

    for f in pipeline.filters:
        share(f)
        line(f"if not {python(f, shared)}:", f)
        lines.append("            continue")
    for name, expr in pipeline.outputs:
        share(expr)
        line(f"out[{name!r}].append({python(expr, shared)})", expr)
    head = ["def pipeline(batch, out):"]
    head += [f"    {c} = batch.column({c!r}).to_pylist()" for c in pipeline.columns()]
    head += ["    for i in range(batch.num_rows):"]
    source = "\n".join(head + [x for x in lines if x.strip() != "count(0)"]) + "\n"
    return Generated(source, len({n for t in trees for n in nodes(t)}))


def _operations(expr: Expression, shared: dict[Expression, str]) -> int:
    """The operations computing ``expr`` runs, leaving out the values already in variables."""
    if expr in shared or not isinstance(expr, Call):
        return 0
    return 1 + sum(_operations(a, shared) for a in expr.args)


@dataclass
class Run:
    """What running a pipeline over some batches counted, one way."""

    result: pa.Table
    dispatches: int = 0
    """Nodes of a tree visited while the rows ran."""
    written: int = 0
    """Bytes of every array written while the rows ran, the result's included."""
    instructions: int = 0
    """Instructions of the vector unit's model: one for every lane-full an operation computed."""


def compiled(pipeline: Pipeline, batches: list[pa.RecordBatch]) -> Run:
    """``pipeline`` compiled once, and its function called on every batch."""
    unit = VectorUnit()
    # The counting code calls count(k) before a line that runs k operations, each on one value.
    scope = {"divide": divide, "count": lambda k: [unit.run(1) for _ in range(k)]}
    exec(compile(generate(pipeline, counting=True).source, "<pipeline>", "exec"), scope)
    out = {name: [] for name, _ in pipeline.outputs}
    for batch in batches:
        scope["pipeline"](batch, out)
    result = pa.table(out)
    return Run(result, 0, result.get_total_buffer_size(), unit.instructions)


def interpreted(pipeline: Pipeline, batches: list[pa.RecordBatch]) -> Run:
    """``pipeline`` interpreted a batch at a time, as ch06's evaluator does: each filter keeps the
    rows its tree's kernels say pass, and hands on a new batch of them; each output column is its
    tree's kernels run over the last batch. Every kernel writes an array."""
    run, unit = Run(pa.table({})), VectorUnit()

    def evaluate(expr: Expression, batch: pa.RecordBatch):
        run.dispatches += 1
        match expr:
            case Column(name):
                return batch.column(name)
            case Literal(value):
                return pa.scalar(value)
            case Call(op, args):
                values = [evaluate(a, batch) for a in args]
                unit.run(batch.num_rows)
                result = KERNELS[op](*values)
                # A kernel over constants alone gives one value, not an array.
                if not isinstance(result, pa.Scalar):
                    run.written += result.get_total_buffer_size()
                return result
        raise TypeError(f"not an expression: {expr!r}")

    outputs = []
    for batch in batches:
        for f in pipeline.filters:
            batch = batch.filter(evaluate(f, batch))
            run.written += batch.get_total_buffer_size()
        columns = [evaluate(e, batch) for _, e in pipeline.outputs]
        outputs.append(pa.RecordBatch.from_arrays(columns, names=[n for n, _ in pipeline.outputs]))
    run.result = pa.Table.from_batches(outputs)
    run.written += run.result.get_total_buffer_size()
    run.instructions = unit.instructions
    return run


def rows_at_a_time(pipeline: Pipeline, batches: list[pa.RecordBatch]) -> Run:
    """``pipeline`` interpreted a row at a time: every node of every tree visited for every row
    that reaches it (ch06). Values pass from node to node in local variables, and nothing is
    written but the result."""
    counts, unit = Counts(), VectorUnit()
    out = {name: [] for name, _ in pipeline.outputs}
    for batch in batches:
        for row in batch.to_pylist():
            if all(evaluate_row(f, row, counts, unit) for f in pipeline.filters):
                for name, expr in pipeline.outputs:
                    out[name].append(evaluate_row(expr, row, counts, unit))
    result = pa.table(out)
    return Run(result, counts.dispatches, result.get_total_buffer_size(), unit.instructions)
