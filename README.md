# Queries, operator by operator

*Build a query engine to learn what a query costs.*

An interactive technical book for data engineers who run queries every day and want to know what
they cost. You build a small query engine in Python on Apache Arrow, one operator at a time, and
measure each operator against DuckDB: rows in and out, batches, bytes read, requests, memory,
spill and shuffle. By the end you can predict how a design choice changes those numbers, in any
engine.

Every chapter follows the same method: **observe** a query in DuckDB and read its plan and
profile, **predict** what an operator will do and **measure** it, **build** the operator,
**compare** it with DuckDB, then say what it means for **your design**.

The book is the second in a series with *[Parquet, byte by byte](https://github.com/snowch/parquet-book)*,
whose Parquet reader is this engine's scan layer.

## Status

Phase 0 (setup and spikes) is mostly done, and the pilot's first chapter is being drafted. See
`PLAN.md` for the plan and its status table.

## Build and read it

```bash
git clone --recurse-submodules https://github.com/snowch/query-engine-book
cd query-engine-book
make install    # pinned DuckDB, pyarrow and MyST; Pyodide for the parity test
make            # figures and site
make serve      # http://localhost:8000
```

You need Python 3.11+ and Node.js 22. `make check` runs everything CI runs, including the
headless-browser probe if Playwright is installed.

## Use it

```bash
PYTHONPATH=python python3 -m query_lab observe queries/returned_unit_price.sql  # DuckDB's plan and profile
python3 fixtures/generate.py --check        # the fixtures are what the generator writes
python3 -m pytest                           # the tests
node spikes/duckdb-pyodide/node.mjs         # the same probe under Pyodide
```

## What is here

| Path | |
|---|---|
| `python/query_lab/` | the engine: counters, the DuckDB reference, the figures |
| `external/parquet-book/` | the Parquet book (submodule); its reader is the scan layer |
| `queries/` | every query the book runs |
| `fixtures/` | seeded datasets written by pyarrow, with manifests |
| `chapters/`, `parts/`, `appendices/` | the book, in MyST markdown |
| `spikes/` | experiments that decided something, with their findings |
| `tools/`, `scripts/`, `tests/`, `web/` | the renderer, the build, the checks, the stylesheet |

## Contributing

Read `CLAUDE.md` first: it holds the rules the build enforces. Then `COUNTERS.md`,
`AUTHORING_GUIDE.md` and `STYLE.md`.

## Licence

The text is CC BY-NC 4.0. The code is Apache 2.0.
