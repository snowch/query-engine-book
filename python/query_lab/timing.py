"""Times, measured live: how long each case of a chapter's experiment takes, where it runs.

Every number the book prints is a counter, the same on every machine and at every build
(COUNTERS.md). A time is not: it differs from run to run and machine to machine, and under
WebAssembly in a browser it is slower than at a desk. So no time is ever written into a page.
A chapter's ``timed`` block names one of the functions here; the page shows its cases, and when
the reader asks, runs each one in the reader's browser and shows how long it took there and then.
At a desk, ``python3 -m query_lab time <name>`` does the same.

What a time is good for is comparing cases with each other, in one run, on one machine: a top-k
against a full sort, a batch at a time against a row at a time. Each function here returns a
:class:`Timing`: its cases, and the comparisons the chapter's prose relies on, which
``python/tests/test_timing.py`` checks at a desk.

Two kinds of case:

- **DuckDB's**, on tables it generates, a million rows or so: the fixtures are small enough that
  DuckDB finishes them faster than a browser's clock can tell apart.
- **The book's engine's**, on the fixtures, as the chapters run it. Its times are mostly Python's:
  slower than DuckDB by far, for reasons that have nothing to do with the plan.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

#: Where an operator's time went: its name, its depth in the plan, and the seconds it spent
#: itself, its children's time left out. Top down, as a plan is read.
Profile = list[tuple[str, int, float]]

#: A case this slow is timed once: the reader waits for every run.
SLOW = 0.5
#: A faster case runs in groups at least this long, so that a coarse clock can time it: some
#: browsers round their clock to a millisecond.
GROUP = 0.05
#: The groups a faster case is timed in; its time is the median.
GROUPS = 3
#: The most runs in one group, however fast a case is.
MOST = 1000


@dataclass
class Case:
    """One thing to time."""

    label: str
    detail: str
    """What runs, shown as code: a query, or the engine's call."""
    work: Callable[[], Profile | None]
    """Runs the case once. It may return a profile of where the time went."""


@dataclass
class Timing:
    """A chapter's timed experiment."""

    title: str
    cases: list[Case]
    data: str = ""
    """What the cases run on, in a sentence: a fixture, or the table DuckDB generates."""
    faster: list[tuple[int, int]] = field(default_factory=list)
    """Pairs ``(a, b)``: the chapter says case ``a`` runs faster than case ``b``."""
    setup: Callable[[], None] = lambda: None
    """Makes what the cases need, a generated table say, once, before any case is timed."""


def where() -> str:
    """Where this Python runs, as the page says it."""
    if sys.platform == "emscripten":
        return "your browser, under WebAssembly, on one thread"
    return f"Python {sys.version.split()[0]} on {sys.platform}"


def clock(work: Callable[[], Profile | None]) -> tuple[float, int, Profile | None]:
    """How long ``work`` takes, in seconds; how many times it ran to say so; and the profile its
    last run returned.

    The first run counts alone when it is slow. Otherwise it was a warm-up, and the case runs in
    groups long enough for any browser's clock, and the time is a group's median, per run.
    """
    start = time.perf_counter()
    profile = work()
    first = time.perf_counter() - start
    if first >= SLOW:
        return first, 1, profile
    per_group = min(MOST, max(1, int(GROUP / max(first, 1e-4)) + 1))
    times = []
    for _ in range(GROUPS):
        start = time.perf_counter()
        for _ in range(per_group):
            profile = work()
        times.append((time.perf_counter() - start) / per_group)
    return statistics.median(times), 1 + GROUPS * per_group, profile


# Profiles.


def engine_profile(plan) -> Callable[[], Profile]:
    """Time every operator of one of the engine's plans as it runs, without changing the engine.

    Each operator's batches are wrapped, so the time spent getting each batch from it is kept:
    that time includes its children's, since an operator asks its children for batches while it
    makes its own. What it spent itself is that less its children's. Call the result after the
    plan has run.
    """
    spent: dict[int, float] = {}

    def wrap(op) -> None:
        inner = op.batches
        spent[id(op)] = 0.0

        def batches():
            it = inner()
            while True:
                start = time.perf_counter()
                try:
                    batch = next(it)
                except StopIteration:
                    spent[id(op)] += time.perf_counter() - start
                    return
                spent[id(op)] += time.perf_counter() - start
                yield batch

        op.batches = batches
        for child in op.children:
            wrap(child)

    wrap(plan)

    def profile() -> Profile:
        out: Profile = []

        def walk(op, depth: int) -> None:
            own = spent[id(op)] - sum(spent[id(c)] for c in op.children)
            out.append((op.metrics.operator, depth, max(0.0, own)))
            for child in op.children:
                walk(child, depth + 1)

        walk(plan, 0)
        return out

    return profile


def duckdb_profile(con, sql: str) -> Profile:
    """Run ``sql`` with DuckDB's profiling on, and the time its profile gives each operator."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        con.execute("PRAGMA enable_profiling = 'json'")
        con.execute(f"PRAGMA profiling_output = '{path}'")
        con.execute(sql).fetchall()
        con.execute("PRAGMA disable_profiling")
        raw = json.loads(Path(path).read_text())
    finally:
        os.unlink(path)
    out: Profile = []

    def walk(node: dict, depth: int) -> None:
        out.append((node["operator_type"], depth, float(node.get("operator_timing", 0.0))))
        for child in node.get("children", []):
            walk(child, depth + 1)

    for child in raw["children"]:
        walk(child, 0)
    return out


# A connection to DuckDB with tables it generated.

#: The rows of DuckDB's generated tables: enough that each case takes tens of milliseconds or
#: more in a browser, few enough that the slowest takes seconds.
ROWS = 1_000_000


class _DuckDB:
    """A connection to DuckDB, with one thread as everywhere in the book, made by :meth:`setup`
    and then given ``statements``: the tables a timing's cases query."""

    def __init__(self, *statements: str) -> None:
        self.statements = statements
        self.con = None

    def setup(self) -> None:
        from .reference import connect

        if self.con is None:
            self.con = connect()
            # A spill goes to a directory of the book's own, at a desk and in a browser alike.
            self.con.execute(f"SET temp_directory = '{tempfile.mkdtemp(prefix='query-lab-')}'")
            for s in self.statements:
                self.con.execute(s)

    def query(self, sql: str) -> Callable[[], None]:
        """A case's work: run ``sql``, and fetch its result."""

        def work() -> None:
            self.con.execute(sql).fetchall()

        return work


def _fixture(root: Path, name: str) -> Path:
    return root / "fixtures" / name


def _ignore(call: Callable[[], object]) -> Callable[[], None]:
    """A case's work from a call whose result the timing does not need."""

    def work() -> None:
        call()

    return work


# One function per timed block, in the chapters' order.


def two_engines(root: Path) -> Timing:
    """ch01: the same plan run by the book's engine and by DuckDB, each with where its time went."""
    from .first_plan import returned_unit_price
    from .reference import connect, read_query

    sql = read_query(root / "queries" / "returned_unit_price.sql")
    con = connect()

    def engine() -> Profile:
        plan = returned_unit_price(root)
        profile = engine_profile(plan)
        plan.run()
        return profile()

    return Timing(
        title="One plan, two engines",
        data="queries/returned_unit_price.sql, on fixtures/orders-sorted.parquet.",
        cases=[
            Case("The book's engine", "returned_unit_price(root).run()", engine),
            Case("DuckDB", "queries/returned_unit_price.sql", lambda: duckdb_profile(con, sql)),
        ],
        faster=[(1, 0)],
    )


#: The values of the gathers' column: more than a cache holds.
GATHER_VALUES = 4_000_000


def gathers(root: Path) -> Timing:
    """ch02: one column gathered in the order it is stored, and in a shuffled order."""
    import pyarrow.compute as pc

    from .reference import connect

    held: dict = {}

    def setup() -> None:
        # DuckDB makes the column and the shuffle: the same on every machine, and quick.
        con = connect()
        n = GATHER_VALUES
        held["values"] = con.execute(f"SELECT hash(i) % 100000 FROM range({n}) t(i)").arrow().column(0)
        held["in order"] = con.execute(f"SELECT i FROM range({n}) t(i)").arrow().column(0)
        held["shuffled"] = con.execute(f"SELECT i FROM range({n}) t(i) ORDER BY hash(i)").arrow().column(0)

    def gather(order: str) -> Callable[[], None]:
        return _ignore(lambda: pc.take(held["values"], held[order]))

    return Timing(
        title="A gather, in order and shuffled",
        data=f"values: {GATHER_VALUES:,} integers, generated by DuckDB; the gather is pyarrow's take.",
        cases=[
            Case("In the order stored", f"take(values, 0 … {GATHER_VALUES - 1:,})", gather("in order")),
            Case("Shuffled", f"take(values, a shuffle of 0 … {GATHER_VALUES - 1:,})", gather("shuffled")),
        ],
        faster=[(0, 1)],
        setup=setup,
    )


def pushdown(root: Path) -> Timing:
    """ch03: the early March orders scanned by the engine with nothing pushed into the scan, with
    the columns pushed, and with the columns and the filter."""
    import pyarrow.compute as pc

    from .operators import Filter, Scan
    from .plans import EARLY_MARCH, ORDERS_COLUMNS

    orders = _fixture(root, "orders-sorted.parquet")
    wanted = ["order_id", "customer_id", "amount", "order_date"]

    def above(columns: list[str]) -> Callable[[], None]:
        def test(batch):
            masks = [c.mask(batch) for c in EARLY_MARCH]
            return pc.and_(*masks)

        return _ignore(lambda: Filter(Scan(orders, columns), "order_date in early March", test).run())

    def pushed() -> None:
        Scan(orders, wanted, EARLY_MARCH).run()

    return Timing(
        title="Pushing work into the scan",
        data="The scan of queries/early_march.sql, by the book's engine, on fixtures/orders-sorted.parquet.",
        cases=[
            Case("Nothing pushed", "Filter(Scan(every column))", above(ORDERS_COLUMNS)),
            Case("The columns pushed", "Filter(Scan(four columns))", above(wanted)),
            Case("The columns and the filter pushed", "Scan(four columns, the filter)", pushed),
        ],
        faster=[(1, 0), (2, 1)],
    )


def pruning(root: Path) -> Timing:
    """ch04: the early March orders from the shuffled file, the sorted one, and the paged one
    read by its page index, the filter pushed into the scan each time."""
    from .operators import Scan
    from .plans import EARLY_MARCH

    columns = ["order_id", "customer_id", "amount"]

    def scan(fixture: str, by_page: bool = False) -> Callable[[], None]:
        return _ignore(lambda: Scan(_fixture(root, fixture), columns, EARLY_MARCH, page_index=by_page).run())

    return Timing(
        title="What the statistics let the scan skip",
        data="The early March orders, by the book's engine, the filter pushed into the scan each time.",
        cases=[
            Case("Shuffled", "orders-shuffled.parquet", scan("orders-shuffled.parquet")),
            Case("Sorted", "orders-sorted.parquet", scan("orders-sorted.parquet")),
            Case(
                "Sorted, by page", "orders-paged.parquet, its page index", scan("orders-paged.parquet", True)
            ),
        ],
        faster=[(1, 0), (2, 1)],
    )


def kernels(root: Path) -> Timing:
    """ch06: queries/with_tax.sql's expressions evaluated a row at a time, and a batch at a time
    in batches of three sizes."""
    from .expressions import batches_of, evaluate, evaluate_row
    from .operators import Scan
    from .plans import WITH_TAX, WITH_TAX_WHERE

    held: dict = {}

    def setup() -> None:
        held["table"] = Scan(_fixture(root, "orders-sorted.parquet"), ["amount", "quantity"]).run()
        held["rows"] = held["table"].to_pylist()

    def by_row() -> None:
        for r in held["rows"]:
            if evaluate_row(WITH_TAX_WHERE, r):
                evaluate_row(WITH_TAX, r)

    def by_batch(size: int) -> Callable[[], None]:
        def work() -> None:
            for batch in batches_of(held["table"], size):
                evaluate(WITH_TAX, batch.filter(evaluate(WITH_TAX_WHERE, batch)))

        return work

    return Timing(
        title="A row at a time, and a batch at a time",
        data="The expressions of queries/with_tax.sql, by the book's engine, over fixtures/orders-sorted.parquet.",
        cases=[
            Case("A row at a time", "evaluate_row, for each row", by_row),
            *(
                Case(f"Batches of {n:,} rows", "evaluate, for each batch", by_batch(n))
                for n in (16, 256, 2048)
            ),
        ],
        faster=[(1, 0), (2, 1), (3, 1)],
        setup=setup,
    )


def branches(root: Path) -> Timing:
    """ch06: the values over fifty kept from a million, stored sorted and stored shuffled, by
    pyarrow's filter, which decides value by value where kept and dropped values mix, and by
    DuckDB, whose kernel has no branch on the data."""
    import pyarrow.compute as pc

    held: dict = {}
    db = _DuckDB(
        f"CREATE TABLE shuffled AS SELECT (hash(i) % 10000) / 100.0 AS v FROM range({ROWS}) t(i)",
        "CREATE TABLE sorted AS SELECT v FROM shuffled ORDER BY v",
    )

    def setup() -> None:
        db.setup()
        for table in ("sorted", "shuffled"):
            held[table] = db.con.execute(f"SELECT v FROM {table}").arrow().column(0)

    def filtered(order: str) -> Callable[[], None]:
        return _ignore(lambda: pc.filter(held[order], pc.greater(held[order], 50)))

    # `v + 0`, so that DuckDB tests every value: a bare `v > 50` lets it skip the sorted table's
    # row groups by their bounds, as ch04's scan does, and the timing would be of that.
    test = "SELECT sum(v) FROM {} WHERE v + 0 > 50"
    return Timing(
        title="One test, two orders of the values",
        data=f"sorted and shuffled: the same {ROWS:,} values from 0 to 100, generated by DuckDB.",
        cases=[
            Case("pyarrow, on the sorted values", "filter(sorted, sorted > 50)", filtered("sorted")),
            Case("pyarrow, on the shuffled values", "filter(shuffled, shuffled > 50)", filtered("shuffled")),
            Case("DuckDB, on the sorted values", test.format("sorted"), db.query(test.format("sorted"))),
            Case(
                "DuckDB, on the shuffled values", test.format("shuffled"), db.query(test.format("shuffled"))
            ),
        ],
        faster=[(0, 1)],
        setup=setup,
    )


#: The numbers of groups the aggregation's cases ask for, from a table that fits a cache to one
#: that does not.
GROUPS_ASKED = (1_000, 100_000, 1_000_000)


def groups(root: Path) -> Timing:
    """ch07: DuckDB grouping a million rows into more and more groups."""
    db = _DuckDB(f"CREATE TABLE t AS SELECT hash(i) AS k, i % 997 AS v FROM range({ROWS}) t(i)")
    cases = []
    for n in GROUPS_ASKED:
        sql = f"SELECT k % {n} AS g, sum(v) FROM t GROUP BY g"
        cases.append(Case(f"Up to {n:,} groups", sql, db.query(sql)))
    return Timing(
        title="More groups, a bigger table",
        data=f"t: {ROWS:,} rows of a hashed key k and a small value v, generated by DuckDB.",
        cases=cases,
        faster=[(0, 2), (1, 2)],
        setup=db.setup,
    )


#: The build sides of the joins' cases.
BUILD_ROWS = (1_000, 100_000, 1_000_000)


def build_sides(root: Path) -> Timing:
    """ch08: DuckDB probing with a million rows a build side of more and more rows."""
    statements = [f"CREATE TABLE probe AS SELECT hash(i) AS k FROM range({ROWS}) t(i)"]
    cases = []
    for n in BUILD_ROWS:
        statements.append(f"CREATE TABLE build_{n} AS SELECT i AS k, i * 2 AS w FROM range({n}) t(i)")
        sql = f"SELECT count(*), sum(w) FROM probe JOIN build_{n} b ON probe.k % {n} = b.k"
        cases.append(Case(f"A build side of {n:,} rows", sql, None))
    db = _DuckDB(*statements)
    for case in cases:
        case.work = db.query(case.detail)
    return Timing(
        title="A bigger build side",
        data=f"probe: {ROWS:,} hashed keys; build_n: the keys 0 to n - 1. Generated by DuckDB.",
        cases=cases,
        faster=[(0, 2), (1, 2)],
        setup=db.setup,
    )


def top_k(root: Path) -> Timing:
    """ch09: DuckDB sorting a million rows, and keeping the first ten of the same order."""
    db = _DuckDB(f"CREATE TABLE t AS SELECT i, (hash(i) % 10000) / 100.0 AS v FROM range({ROWS}) t(i)")
    full = "CREATE OR REPLACE TEMP TABLE sorted AS SELECT * FROM t ORDER BY v"
    top = "SELECT * FROM t ORDER BY v LIMIT 10"
    return Timing(
        title="Sort everything, or keep ten",
        data=f"t: {ROWS:,} rows of i and a value v, generated by DuckDB.",
        cases=[Case("Every row, sorted", full, db.query(full)), Case("The first ten", top, db.query(top))],
        faster=[(1, 0)],
        setup=db.setup,
    )


#: The memory limits of the spilling's cases: none to speak of, then one that makes DuckDB spill.
MEMORY_LIMITS = ("4GB", "16MB")


def spilling(root: Path) -> Timing:
    """ch10: DuckDB sorting a million rows within less and less memory."""
    db = _DuckDB(f"CREATE TABLE t AS SELECT i, (hash(i) % 10000) / 100.0 AS v FROM range({ROWS}) t(i)")
    sort = "CREATE OR REPLACE TEMP TABLE sorted AS SELECT * FROM t ORDER BY v"
    cases = []
    for limit in MEMORY_LIMITS:
        limited = db.query(f"SET memory_limit = '{limit}'")
        sorting = db.query(sort)
        cases.append(
            Case(
                f"A memory limit of {limit}",
                f"SET memory_limit = '{limit}'; {sort}",
                lambda limited=limited, sorting=sorting: limited() or sorting(),
            )
        )
    return Timing(
        title="One sort, less memory",
        data=f"t: {ROWS:,} rows of i and a value v, generated by DuckDB, sorted into a table each time.",
        cases=cases,
        faster=[(0, 1)],
        setup=db.setup,
    )


def rules(root: Path) -> Timing:
    """ch12: ch11's enterprise orders planned by the engine the plain way, with each rule, and
    with both."""
    from .planner import plan
    from .reference import read_query
    from .rules import prune_columns, push_filters

    text = read_query(root / "queries" / "enterprise_orders.sql")

    def run(chosen: tuple) -> Callable[[], None]:
        return _ignore(lambda: plan(root, text, chosen).run())

    return Timing(
        title="Four plans, timed",
        data="queries/enterprise_orders.sql, planned and run by the book's engine on the fixtures.",
        cases=[
            Case("The plain plan", "no rules", run(())),
            Case("Push the filters down", "push_filters", run((push_filters,))),
            Case("Prune the columns", "prune_columns", run((prune_columns,))),
            Case("Both rules", "push_filters, then prune_columns", run((push_filters, prune_columns))),
        ],
        faster=[(2, 0), (2, 1), (3, 0)],
    )


#: How many copies of the orders the join order's cases join: a million rows.
ORDER_COPIES = 50


def join_order(root: Path) -> Timing:
    """ch13: queries/asian_orders.sql run by DuckDB on fifty copies of the orders, in the order
    its optimiser chooses, and in the order the query is written."""
    fixtures = root / "fixtures"
    db = _DuckDB(
        f"CREATE TABLE o AS SELECT o.* FROM '{fixtures}/orders-sorted.parquet' o, range({ORDER_COPIES})",
        f"CREATE TABLE c AS SELECT * FROM '{fixtures}/customers.parquet'",
        f"CREATE TABLE n AS SELECT * FROM '{fixtures}/countries.parquet'",
    )
    sql = (
        "SELECT count(*), max(c.name), max(n.name) FROM o "
        "JOIN c ON o.customer_id = c.customer_id JOIN n ON c.country = n.country WHERE n.region = 'Asia'"
    )
    chosen, written = (
        db.query(f"SET disabled_optimizers = ''; {sql}"),
        db.query(f"SET disabled_optimizers = 'join_order'; {sql}"),
    )
    return Timing(
        title="The order the optimiser chooses, and the order written",
        data=f"o: the orders, {ORDER_COPIES} times over; c and n: the customers and the countries.",
        cases=[
            Case("The optimiser's order", sql, chosen),
            Case("As written", f"SET disabled_optimizers = 'join_order'; {sql}", written),
        ],
        faster=[(0, 1)],
        setup=db.setup,
    )


def compiling(root: Path) -> Timing:
    """ch19: ch01's pipeline over the sorted orders interpreted a row at a time, interpreted a
    batch at a time, and compiled into one loop of Python, none of them counting as it runs."""
    from .compile import Pipeline, divide, generate, interpreted
    from .expressions import evaluate_row
    from .operators import Scan
    from .reference import read_query

    pipeline = Pipeline.of(read_query(root / "queries" / "returned_unit_price.sql"))
    batches: list = []
    scope = {"divide": divide}

    def setup() -> None:
        batches.extend(Scan(_fixture(root, "orders-sorted.parquet"), pipeline.columns()).batches())
        exec(compile(generate(pipeline).source, "<pipeline>", "exec"), scope)

    def by_row() -> None:
        out = {name: [] for name, _ in pipeline.outputs}
        for batch in batches:
            for row in batch.to_pylist():
                if all(evaluate_row(f, row) for f in pipeline.filters):
                    for name, expr in pipeline.outputs:
                        out[name].append(evaluate_row(expr, row))

    def by_loop() -> None:
        out = {name: [] for name, _ in pipeline.outputs}
        for batch in batches:
            scope["pipeline"](batch, out)

    return Timing(
        title="Three ways to run one pipeline",
        data="ch01's pipeline, by the book's engine, over fixtures/orders-sorted.parquet.",
        cases=[
            Case("Interpreted, a row at a time", "ch06's evaluate_row", by_row),
            Case(
                "Interpreted, a batch at a time",
                "ch06's evaluate, a kernel a node",
                _ignore(lambda: interpreted(pipeline, batches)),
            ),
            Case("Compiled into one loop of Python", "generate, then compile", by_loop),
        ],
        faster=[(2, 0), (1, 2)],
        setup=setup,
    )


TIMINGS: dict[str, Callable[[Path], Timing]] = {
    "two_engines": two_engines,
    "gathers": gathers,
    "pushdown": pushdown,
    "pruning": pruning,
    "kernels": kernels,
    "branches": branches,
    "groups": groups,
    "build_sides": build_sides,
    "top_k": top_k,
    "spilling": spilling,
    "rules": rules,
    "join_order": join_order,
    "compiling": compiling,
}


class TimingError(ValueError):
    """A ``timed`` block named a timing that does not exist."""


def timing(root: Path, name: str) -> Timing:
    if name not in TIMINGS:
        raise TimingError(f"no timing {name!r}; the timings are {', '.join(TIMINGS)}")
    return TIMINGS[name](root)


def json_name(name: str) -> str:
    """The file a timed block's cases live in, under ``chapters/_generated/``."""
    return f"timing-{name.replace('_', '-')}.json"


def describe(root: Path, name: str) -> dict:
    """What the page shows before anything is timed: the title and the cases. No time."""
    t = timing(root, name)
    return {
        "of": name,
        "title": t.title,
        "data": t.data,
        "cases": [{"label": c.label, "detail": c.detail} for c in t.cases],
    }


#: Each timing as built for this Python, so its setup runs once however many cases are timed.
_built: dict[str, Timing] = {}


def warm_up() -> None:
    """Make the first call of each kind of kernel before anything is timed.

    Under WebAssembly the first comparison of strings takes seconds, once, while pyarrow readies
    it: timed, it would be charged to whichever case happened to run first.
    """
    import pyarrow as pa
    import pyarrow.compute as pc

    strings, numbers = pa.array(["a", "b"]), pa.array([1.0, 2.0])
    pc.equal(strings, "a")
    pc.greater(pc.divide(numbers, numbers), 1)
    pc.take(numbers, pa.array([1, 0]))


def time_case(root: Path, name: str, index: int) -> dict:
    """Time one case of a timing here and now: what the page draws when the reader asks."""
    if not _built:
        warm_up()
    if name not in _built:
        t = timing(root, name)
        t.setup()
        _built[name] = t
    case = _built[name].cases[index]
    seconds, runs, profile = clock(case.work)
    return {
        "seconds": seconds,
        "runs": runs,
        "profile": [list(p) for p in profile] if profile else None,
        "where": where(),
    }


def main(root: Path, name: str) -> int:
    """Time every case of a timing at a desk, and print the times."""
    t = timing(root, name)
    print(f"{t.title}: timed with {where()}\n")
    width = max(len(c.label) for c in t.cases)
    for i, case in enumerate(t.cases):
        result = time_case(root, name, i)
        print(f"  {case.label:<{width}}  {result['seconds'] * 1000:10.1f} ms  ({result['runs']} runs)")
        for operator, depth, seconds in result["profile"] or []:
            print(f"    {'  ' * depth}{operator:<{24 - 2 * depth}} {seconds * 1000:10.1f} ms")
    return 0
