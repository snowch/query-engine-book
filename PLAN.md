# PLAN.md: Queries, operator by operator

**Queries, operator by operator**
*Build a query engine to learn what a query costs*

The title matches *Parquet, byte by byte*, so the two read as a series. It says how the book is
organised (one operator at a time), and the subtitle states the performance promise. If an Arrow
book ever happens, *Arrow, buffer by buffer* completes the set.

Alternatives, if the performance angle should come first:

- **What a Query Costs**: *Build an engine, measure every operator*
- **The Cost of a Query**: *An engine you build, run and measure*

## 1. The book in one paragraph

**Promise:** understand what a query costs by building the thing that pays for it.

**Readers:** data engineers who use query engines daily but haven't gone deep on performance.
They need Python and nothing else. The book is self-contained; the Parquet and computer-systems
books are optional depth.

**Goal:** the reader can predict how a design choice will change bytes read, rows moved, memory
used and data shuffled, in any engine, including Vast DataBase.

## 2. Decisions

- **Python only.** The engine is built on Arrow and `pyarrow.compute`.
- **The Parquet book's reader is the scan layer,** imported as a package, not copied.
- **DuckDB is the single reference engine.** It's used as a library in the browser (Pyodide) and
  at the desk, with its version pinned.
- **Counters, not time, in the browser.** Timing labs are optional and run at the desk.
- **Small simulators for CPU concepts:** a cache model, a 2-bit branch predictor, and a SIMD lane
  view.
- **Self-contained.** Hardware and format concepts are introduced at the point they're first
  needed, each with a deliberately small model.
- **Every chapter follows observe, build, compare, then design.**
- **Vendor-neutral.** Vast DataBase appears as one worked example of pushing work into storage.
- **Grove is credited, not followed.** Chapters are written from primary sources, in our own
  order.

## 3. Chapter template

1. **The question**, and why the previous chapter left it open.
2. **Observe:** run the query in DuckDB and read its plan and JSON profile.
3. **Predict, then measure:** the reader commits a guess, then runs the experiment.
4. **Building it:** the operator's code, quoted from the working tree.
5. **Compare:** check results and counters against DuckDB.
6. **What this cannot tell you.**
7. **What this means for your design.**
8. **Key takeaways.**
9. **Problems:** kernels for the reader to write, scored by tests and simulators, plus one
   "diagnose the slow query" exercise.
10. **Where to go next:** papers, engine source code, and the other books as optional depth.

`tools/outline.CHAPTER_SHAPE` holds these headings, and `tests/test_book.py` holds every chapter
to them.

## 4. Phase 0: setup and spikes

- **Repo:** create `snowch/query-engine-book` from the Parquet book's tooling. Copy it for now
  and extract a shared package once both books are stable.
- **Spike: DuckDB under Pyodide.** It must load, query a fixture held in Pyodide's in-memory
  filesystem, and produce a JSON profile.
- **Spike: the Parquet reader** imports as a dependency, in the browser and at the desk.
- **Spike: panels** drawn without Rust, from Python or JS.
- **Counters spec:** one metrics structure every operator reports (rows in and out, batches,
  bytes read, peak memory, bytes spilled, bytes shuffled). Settle this first, since everything
  builds on it.
- **Fixture generator:** seeded datasets with controlled properties such as sorted and shuffled
  order, skewed keys, chosen cardinalities, and a small dimension table.
- **Build checks:** no typed numbers; no pasted code; a glossary-order check (no term used before
  the chapter that defines it); parity tests against DuckDB.

## 5. Phase 1: pilot slice (go/no-go)

1. **The plan is the map.** `EXPLAIN` one query in DuckDB, then run a hand-written plan through
   your scan, filter and projection.
2. **Reading less.** Push projection and filters into the Parquet scan and count the bytes and
   row groups skipped.
3. **Batches in memory.** Build Arrow arrays from raw buffers, decode the validity bitmap, and
   run sorted versus shuffled `take` through the cache simulator.

**Go/no-go criteria:**

- Does "predict, then measure" feel illuminating?
- How many hours did each chapter take?
- Can a test reader who hasn't read the other books follow it?

If any of these fail, change the approach before writing more.

## 6. Phase 2: draft table of contents

- **Part I, Seeing a query:** the plan is the map; operators and batches (pulling versus pushing
  data); batches in memory.
- **Part II, Reading less:** projection and filter pushdown; statistics and pruning; where work
  happens (the scan, Iceberg metadata, storage that evaluates predicates).
- **Part III, Computing:** expressions and vectorised kernels (branch simulator, SIMD lanes);
  hash aggregation; joins (build side, the cache cliff); sorting and top-k; memory limits and
  spilling.
- **Part IV, Planning:** from SQL to a logical plan; optimiser rules; statistics, cost and join
  order.
- **Part V, Scaling out:** parallelism on one machine (a desk lab with DuckDB's thread setting);
  partitioning and shuffle; skew; stages and distributed execution, simulated locally with
  counters for bytes moved, and Spark, Trino and Ballista described in prose.
- **Part VI, Beyond Python (optional):** what a compiled engine changes, reading one DuckDB
  operator in C++.
- **Appendices:** running the lab; the fixtures; the machine in one page; the glossary.

## 7. Risks and guardrails

- **Capacity.** Freeze or finish the Parquet book first, since it's effectively volume one.
  Nothing beyond the pilot until it passes go/no-go.
- **Scope creep.** Arrow material stays inside this book unless it outgrows two chapters.
- **Closeness to Grove.** Keep a source list for each chapter, and never mirror his order or
  examples.
- **Oversimplified simulators.** Every chapter that uses one says what the model leaves out.
- **Version drift.** DuckDB is pinned. Upgrading is a deliberate commit that regenerates the
  tables.

## 8. This week

1. Create the repo from the Parquet book's tooling.
2. Run the DuckDB-in-Pyodide spike, including JSON profiling.
3. Write the counters spec.
4. Build the fixture generator with its first two datasets.
5. Draft chapter 1's question and experiment only.

## 9. Status

What the first week produced, and the decisions it forced. Each links to where the detail lives.

| Item | State | Where |
|---|---|---|
| Repo from the Parquet book's tooling | Done: outline, MyST parse, renderer, site build, number and link checks, CI. Rust, WebAssembly and tab sets removed. | `tools/`, `scripts/`, `.github/` |
| DuckDB-in-Pyodide spike | Passed: desk, Pyodide in Node and Pyodide in Chromium print identical results, plans and profile counters. | `spikes/duckdb-pyodide/` |
| Parquet reader as a dependency | Passed, as a pinned submodule. | `external/parquet-book`, `python/tests/test_scan_layer.py` |
| Counters spec | Written, implemented, tested. | `COUNTERS.md`, `python/query_lab/metrics.py` |
| Fixture generator | `orders` (sorted and shuffled) and `customers`. | `fixtures/generate.py` |
| Build checks | No typed numbers, no pasted code, glossary order, desk-browser parity. Engine-versus-DuckDB parity waits for the engine. | `tests/`, `scripts/verify-numbers.py` |
| Chapter 1 | Written: DuckDB observed, predict then reveal, the engine's scan, filter and project, compared with DuckDB operator by operator, and three problems (two graded, one slow query to diagnose). | `chapters/the_plan_is_the_map.md`, `python/query_lab/operators.py`, `exercises/` |
| Cover page | As in sizing-and-tco: the site's front page, before the preface. | `cover.md` |
| Panels spike | Passed: `query_lab.report` computes each panel's JSON, the build embeds it, JavaScript draws it, and the page can recompute it under Pyodide. The first panel, the plan, is in ch01. | `spikes/panels/`, `web/lab/` |

Decisions taken this week:

- **The pinned versions are Pyodide 0.27.7, DuckDB 1.1.2 and pyarrow 18.1.0.** 0.27.7 is the
  newest Pyodide that ships both DuckDB and pyarrow. The desk pins the same versions, and DuckDB
  runs with one thread in both places. DuckDB's own Pyodide wheels go no further than 1.2.0, on
  the same Pyodide; 1.2.0 was verified to work and to agree with the desk, and moving to it is
  open (`spikes/duckdb-pyodide/README.md`, finding 1).
- **The Parquet reader comes in as a git submodule.** A `pyproject.toml` in the Parquet book's
  `python/` directory would allow a pinned `pip install` from Git instead; that belongs with the
  shared-tooling extraction.
- **A seventh counter, `requests`.** The scan layer already counts requests to its object store,
  and requests are what make object storage slow (COUNTERS.md).
- **DuckDB's scanned-rows counter is never compared.** In 1.1.2 it reports every row in the file
  even when row groups are skipped (COUNTERS.md; `test_duckdbs_rows_scanned_does_not_show_pruning`).
- **Book order follows the table of contents, not the pilot's list.** The pilot's three chapters
  appear in the order Part I then Part II gives them: the plan is the map, batches in memory,
  then projection and filter pushdown. Reorder `tools/outline.py` if the pilot should read in
  its listed order instead.
- **The first browser run is a large download** (the spike measured the runtime, DuckDB, pyarrow
  and pyarrow's dependencies at the CDN). The page must say so and load DuckDB only on demand.
- **Panels draw from the build first.** Each panel's JSON is computed at build time and embedded,
  so it draws with nothing downloaded; *Run it in your browser* recomputes it under Pyodide, with
  DuckDB alone, and the page says whether the answers agree (`spikes/panels/README.md`).
- **A run has one exhibit, and it asks before it answers.** The plan panel replaces the profile
  table: it takes the reader's prediction per operator, hides the measurement until they reveal
  it, then draws prediction, estimate and measurement together. Without JavaScript a panel says
  it needs JavaScript; there is no static copy. Queries in a panel can be edited and rerun.
- **DuckDB stays at 1.1.2.** DuckDB's own Pyodide wheels reach 1.2.0 at most; not worth leaving
  Pyodide's CDN for.
