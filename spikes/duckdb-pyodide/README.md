# Spike: DuckDB and the Parquet book's reader under Pyodide

PLAN.md, Phase 0, asks three things before any chapter is written:

1. Does DuckDB load under Pyodide, query a fixture held in Pyodide's in-memory file system, and
   write a JSON profile?
2. Does the Parquet book's reader import as a dependency, at a desk and in the browser?
3. Do the desk and the browser agree, so a number generated at build time is the number a
   reader sees in the page?

All three: **yes**, with one version constraint. The probe in this directory is the evidence,
and `tests/test_pyodide.py` keeps it true.

## What was run

`probe.py` runs every query in `queries/` through `query_lab.reference.observe` (result,
`EXPLAIN` plan, JSON profile read into `query_lab.metrics`), then the Parquet book's `scan` on
both orders fixtures with the predicate `order_id < 500`. It prints one JSON document.

| Where | Command | Result |
|---|---|---|
| Desk (CPython 3.11) | `python3 spikes/duckdb-pyodide/probe.py` | the reference document |
| Pyodide in Node | `node spikes/duckdb-pyodide/node.mjs` | identical, byte for byte |
| Pyodide in headless Chromium | `node spikes/duckdb-pyodide/browser.mjs` | identical, byte for byte |

Identical means the same result rows (floats included), the same `EXPLAIN` drawing, the same
per-operator row counts from the profile, and the same bytes fetched and requests made by the
Parquet book's scan.

## Finding 1: pin Pyodide 0.27.7, DuckDB 1.1.2, pyarrow 18.1.0

Pyodide's own distribution carried DuckDB for a while and then stopped:

| Pyodide | Python | DuckDB | pyarrow |
|---|---|---|---|
| 0.26.4 | 3.12 | 1.0.0 | none |
| **0.27.7** | 3.12 | **1.1.2** | **18.1.0** |
| 0.28.3 | 3.13 | none | none |
| 0.29.3 | 3.13 | none | 22.0.0 |

0.27.7 is the newest release that ships both, so the book pins it, and pins the same DuckDB
and pyarrow at the desk (`requirements.txt`). Plans and profiles differ between DuckDB versions,
so the desk must run the browser's version for generated figures to match the page.

The cost is age: DuckDB 1.1.2 and pyarrow 18.1.0 date from late 2024.

**DuckDB's own Pyodide wheels do not change that much** (checked once the environment allowed
`duckdb.github.io`). The `duckdb-pyodide` project's index lists wheels up to DuckDB 1.2.0, and
its newest are built for Pyodide's 2024 ABI, the one 0.27.x uses. None exist for the 2025 ABI
(Pyodide 0.28 and later), and probing for unlisted versions from 1.2.1 to 1.5.6 found none. So
the newest browser DuckDB is 1.2.0, on the Pyodide the book already pins:

| Check, DuckDB 1.2.0 on Pyodide 0.27.7 | Result |
|---|---|
| Loads from `duckdb.github.io` beside Pyodide's pyarrow 18.1.0 | yes |
| Served with `access-control-allow-origin: *`, so a page can fetch it | yes |
| Probe under Node against a desk running DuckDB 1.2.0 | identical, byte for byte |
| `python/tests` with DuckDB 1.2.0 at the desk | all pass, finding 3 included |
| Plans and counters against 1.1.2 | same row counts; the plan drawing differs (1.2.0 no longer prints the `IS NOT NULL` half of a pushed filter) |

Moving to 1.2.0 would be one minor version newer, loaded from a project that has not published
since, instead of from Pyodide's own CDN. It stays a deliberate commit: change the pin in
`requirements.txt`, load the wheel by URL in the page and in `node.mjs` and `page.html`, and
regenerate every fixture and figure (PLAN.md, *Version drift*). Node's built-in fetch ignores
`HTTPS_PROXY`; behind a proxy, run `node.mjs` with `NODE_USE_ENV_PROXY=1` to load a wheel by URL.

## Finding 2: the JSON profile works, with one thread

`PRAGMA enable_profiling = 'json'` and `PRAGMA profiling_output = '<path>'` write the profile to
Pyodide's in-memory file system, and Python reads it back. DuckDB has one thread under Pyodide,
so `query_lab.reference` sets `threads = 1` at the desk too. With that, the plans match.

## Finding 3: DuckDB's `operator_rows_scanned` does not show pruning

On `orders-sorted`, a date filter that lets DuckDB skip most row groups still reports every row
in the file as scanned. So the book compares DuckDB's output rows, never its scanned rows, and
measures bytes skipped with its own scan. COUNTERS.md records this, and
`python/tests/test_metrics.py` fails if a DuckDB upgrade changes it.

## Finding 4: the Parquet book's reader is a submodule

`external/parquet-book` is a git submodule pinned to one commit of `snowch/parquet-book`. At a
desk, `pyproject.toml` puts `external/parquet-book/python` on pytest's path; in the page,
`scripts/build-site.py` copies `parquet_lab`'s modules next to the engine's, as the Parquet
book does for its own. Nothing is copied into this repository's history, and
`python/tests/test_scan_layer.py` fails if a copy appears.

The alternative, `pip install "parquet-lab @ git+https://github.com/snowch/parquet-book@<sha>#subdirectory=python"`,
needs a `pyproject.toml` in the Parquet book's `python/` directory. That is a small change to
the other repository, and a better end state: no submodule for readers to initialise. It was
left for when the two books extract their shared tooling (PLAN.md, Phase 0).

## Finding 5: the first load is large

A reader's first run downloads the Pyodide runtime and standard library, then DuckDB and pyarrow
with pyarrow's dependencies (numpy and pandas). At the CDN those files come to about 43 MB, and
the whole start took about 16 seconds in headless Chromium here. The browser caches them after
that. The page must say so before it starts, and load DuckDB only when a reader runs something
that needs it. The Parquet book already does this for pyarrow.

## Running the browser half

`browser.mjs` needs Playwright and a Chromium. It answers the page's requests for repository
files itself (`page.route`), so there is no server to start; Pyodide and its packages come from
the CDN, as they do for a reader. Behind an HTTPS proxy that re-signs traffic with its own
certificate authority, set `BROWSER_EXTRA_CA` to that authority's certificate. Chromium then
trusts that one key and still checks every certificate.
