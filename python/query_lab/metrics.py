"""The counters every operator reports: one structure, the same for every operator in the book.

COUNTERS.md is the specification; this module is its implementation, and the tests hold the two
together. Every number a page carries about a run is a counter, because counters are the same on
every machine and in the browser, and a time is not: times are measured live, in the reader's
browser, by :mod:`query_lab.timing`. A counter is an exact integer
the operator counts as it runs, never an estimate and never a sample.

An operator owns one :class:`Metrics`. A plan is a tree of operators, so its metrics are a tree
too: :attr:`Metrics.children` are the metrics of the operators that feed this one, in the order
the plan lists them. :func:`from_duckdb_profile` reads DuckDB's JSON profile into the same tree, so
the book can put the two engines' counters side by side.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field, fields

#: The counters, in the order COUNTERS.md defines them and every table in the book prints them.
COUNTERS = (
    "rows_in",
    "rows_out",
    "batches_in",
    "batches_out",
    "bytes_read",
    "requests",
    "peak_memory_bytes",
    "bytes_spilled",
    "bytes_shuffled",
)


class MetricsError(ValueError):
    """A metrics tree that breaks one of COUNTERS.md's invariants."""


@dataclass
class Metrics:
    """What one operator did. Every field but the first two is a count, starting at zero."""

    operator: str
    """The operator's kind, as the plan names it: ``Scan``, ``Filter``, ``Project``."""
    detail: str = ""
    """What distinguishes this operator from others of its kind: a predicate, a column list."""

    rows_in: int = 0
    """Rows the operator consumed. For a leaf (a scan), rows it decoded from storage; for any
    other operator, the sum of its children's ``rows_out``."""
    rows_out: int = 0
    """Rows the operator produced for its parent."""
    batches_in: int = 0
    """Batches consumed: for a leaf, batches decoded; otherwise the children's ``batches_out``."""
    batches_out: int = 0
    """Batches produced, empty ones included."""
    bytes_read: int = 0
    """Bytes fetched from storage, as the object store logged them. Leaves only."""
    requests: int = 0
    """Requests made to storage. Leaves only."""
    peak_memory_bytes: int = 0
    """The high-water mark of Arrow buffer bytes the operator itself held at one time. An
    operator that streams one batch at a time reports its largest batch."""
    bytes_spilled: int = 0
    """Bytes written to temporary storage because they did not fit in the memory limit."""
    bytes_shuffled: int = 0
    """Bytes sent to another partition or worker."""

    children: list[Metrics] = field(default_factory=list)

    def walk(self) -> Iterator[Metrics]:
        """This operator and every operator below it, parents before children."""
        yield self
        for child in self.children:
            yield from child.walk()

    def total(self, counter: str) -> int:
        """A counter summed over the whole tree: the plan's bytes read, say."""
        if counter not in COUNTERS:
            raise KeyError(f"no counter {counter!r}; the counters are {', '.join(COUNTERS)}")
        return sum(getattr(m, counter) for m in self.walk())

    def check(self) -> None:
        """Raise :class:`MetricsError` if the tree breaks an invariant in COUNTERS.md."""
        for m in self.walk():
            for name in COUNTERS:
                if getattr(m, name) < 0:
                    raise MetricsError(f"{m.operator}: {name} is negative")
            if m.children:
                rows = sum(c.rows_out for c in m.children)
                batches = sum(c.batches_out for c in m.children)
                if m.rows_in != rows:
                    raise MetricsError(f"{m.operator}: rows_in is {m.rows_in}, its children produced {rows}")
                if m.batches_in != batches:
                    raise MetricsError(
                        f"{m.operator}: batches_in is {m.batches_in}, its children produced {batches}"
                    )
                if m.bytes_read or m.requests:
                    raise MetricsError(f"{m.operator}: only a leaf reads storage")
            if m.batches_out == 0 and m.rows_out:
                raise MetricsError(f"{m.operator}: rows came out in no batches")

    def __str__(self) -> str:
        """The tree as a table, one operator a line, each indented under its parent, with the
        counters a reader looks at first: rows in and out, batches out and bytes read."""
        names = [("  " * depth + m.operator, m) for m, depth in self._depths(0)]
        width = max(len(n) for n, _ in names)
        lines = [" " * width + "".join(h.rjust(12) for h in ("rows in", "rows out", "batches", "bytes read"))]
        for name, m in names:
            counts = (m.rows_in, m.rows_out, m.batches_out, m.bytes_read)
            lines.append(name.ljust(width) + "".join(f"{c:,}".rjust(12) for c in counts))
        return "\n".join(lines)

    def _depths(self, depth: int) -> Iterator[tuple[Metrics, int]]:
        yield self, depth
        for child in self.children:
            yield from child._depths(depth + 1)

    def to_json(self) -> dict:
        """The tree as JSON, counters in COUNTERS order, for figures, the page and the tests."""
        out: dict = {"operator": self.operator, "detail": self.detail}
        out.update({name: getattr(self, name) for name in COUNTERS})
        out["children"] = [c.to_json() for c in self.children]
        return out

    @staticmethod
    def from_json(j: dict) -> Metrics:
        known = {f.name for f in fields(Metrics)} - {"children"}
        m = Metrics(**{k: v for k, v in j.items() if k in known})
        m.children = [Metrics.from_json(c) for c in j.get("children", [])]
        return m


def from_duckdb_profile(profile: dict) -> Metrics:
    """DuckDB's JSON profile (``PRAGMA enable_profiling = 'json'``) as a :class:`Metrics` tree.

    DuckDB reports fewer counters than the book's engine, so the rest stay zero. What maps, for
    DuckDB 1.1 (COUNTERS.md has the table):

    - ``operator_type`` is the operator; ``extra_info`` is flattened into the detail.
    - ``operator_cardinality`` is ``rows_out``.
    - A leaf's ``rows_in`` is ``operator_rows_scanned``; any other operator's is its children's
      ``rows_out``, as for the book's engine.

    DuckDB reports no batches, bytes or memory per operator in this profile, so those counters are
    left at zero and the book never compares them with DuckDB's.
    """
    # The profile's root is the query, not an operator: its one child is the plan's root.
    root = profile["children"][0] if "operator_type" not in profile else profile
    return _duckdb_operator(root)


def _duckdb_operator(node: dict) -> Metrics:
    children = [_duckdb_operator(c) for c in node.get("children", [])]
    m = Metrics(
        operator=str(node.get("operator_type") or node.get("operator_name") or "?"),
        detail=_detail(node.get("extra_info")),
        rows_out=int(node.get("operator_cardinality", 0)),
        children=children,
    )
    m.rows_in = sum(c.rows_out for c in children) if children else int(node.get("operator_rows_scanned", 0))
    return m


def _detail(extra: object) -> str:
    if isinstance(extra, dict):
        parts = []
        for key, value in extra.items():
            text = value if isinstance(value, str) else ", ".join(map(str, value)) if value else ""
            parts.append(f"{key}: {text}" if text else key)
        return "; ".join(parts)
    return str(extra or "")
