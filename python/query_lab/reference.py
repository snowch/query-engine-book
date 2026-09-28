"""DuckDB, the book's reference engine: run a query and keep what it says about the run.

Every chapter observes a query in DuckDB before building anything: its result, its plan, and its
JSON profile. This module is the one place the book runs DuckDB, so the figures at build time,
the tests, and the page under Pyodide all run it the same way:

- **One thread.** DuckDB in the browser (Pyodide) has one thread, so the desk uses one too, and
  the two give the same plan and the same counters. The parallelism chapter changes this setting
  on purpose, at a desk.
- **The pinned version.** ``requirements.txt`` pins the DuckDB that Pyodide ships. A plan printed
  in the book is the plan that version makes.
- **Counters, not times.** The profile's timings are kept in the raw JSON but never shown: they
  differ on every run and every machine. :func:`query_lab.metrics.from_duckdb_profile` keeps
  the counters.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import duckdb

from .metrics import Metrics, from_duckdb_profile


@dataclass
class Observation:
    """What DuckDB said about one run of one query."""

    sql: str
    columns: list[str]
    rows: list[tuple]
    plan: str
    """``EXPLAIN``'s physical plan, as DuckDB draws it."""
    profile: dict
    """The JSON profile, as DuckDB wrote it."""

    @property
    def metrics(self) -> Metrics:
        return from_duckdb_profile(self.profile)


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET threads = 1")
    return con


def clean_sql(text: str) -> str:
    """A query as ``observe`` runs it: less its comment lines and its closing semicolon, so it can
    follow ``EXPLAIN``. The same for a file in ``queries/`` and a query a reader edited."""
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("--")]
    return "\n".join(lines).strip().rstrip(";").strip()


def read_query(path: str | Path) -> str:
    """A query from ``queries/``, cleaned by :func:`clean_sql`."""
    return clean_sql(Path(path).read_text())


def explain(sql: str, con: duckdb.DuckDBPyConnection | None = None) -> dict:
    """DuckDB's physical plan for ``sql``, as the JSON ``EXPLAIN (FORMAT JSON)`` returns: the top
    operator, with its children below it. Nothing is run."""
    con = con or connect()
    return json.loads(con.execute(f"EXPLAIN (FORMAT JSON) {sql}").fetchall()[0][1])[0]


def observe(sql: str, con: duckdb.DuckDBPyConnection | None = None) -> Observation:
    """Run ``sql`` once for its plan and once, profiled, for its result and counters."""
    con = con or connect()
    plan = con.execute(f"EXPLAIN {sql}").fetchall()[0][1]
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        con.execute("PRAGMA enable_profiling = 'json'")
        con.execute(f"PRAGMA profiling_output = '{path}'")
        result = con.execute(sql)
        columns = [d[0] for d in result.description]
        rows = result.fetchall()
        con.execute("PRAGMA disable_profiling")
        profile = json.loads(Path(path).read_text())
    finally:
        os.unlink(path)
    return Observation(sql=sql, columns=columns, rows=rows, plan=plan, profile=profile)


def bytes_read(sql: str) -> int:
    """The bytes DuckDB reads from files to run ``sql``, counted at the file system (ch03).

    DuckDB's profile reports no bytes, so the book gives DuckDB a file system of its own, through
    fsspec, that counts every read it serves. It needs fsspec, which only the book's build
    installs: the figures that print this count are computed when the book is built, never in
    the page.
    """
    from fsspec.implementations.local import LocalFileSystem  # noqa: PLC0415

    served: list[int] = []

    class Counting(LocalFileSystem):
        protocol = "counted"

        @classmethod
        def _strip_protocol(cls, path):
            return super()._strip_protocol(str(path).removeprefix("counted://"))

        def _open(self, path, mode="rb", **kwargs):
            f = super()._open(path, mode, **kwargs)
            read = f.read

            def counted(n=-1):
                data = read(n)
                served.append(len(data))
                return data

            f.read = counted
            return f

    con = connect()
    con.register_filesystem(Counting())
    con.execute(sql.replace("'fixtures/", f"'counted://{Path.cwd()}/fixtures/")).fetchall()
    return sum(served)
