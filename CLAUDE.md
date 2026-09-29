# CLAUDE.md

Project instructions for anyone, human or AI, working on this book. They are binding.

## What this is

*Queries, operator by operator: build a query engine to learn what a query costs.* An
interactive technical book for data engineers, in which the reader builds a small query engine
in Python on Apache Arrow, one operator at a time, and measures every operator against DuckDB.
Each chapter follows the same method: observe a query in DuckDB, predict what an operator will
do and measure it, build the operator, compare it with DuckDB, then say what it means for the
reader's own designs.

Read **PLAN.md** for the argument, the settled decisions and the status; **COUNTERS.md** before
touching anything an operator reports; **AUTHORING_GUIDE.md** before writing or editing a page;
and **STYLE.md** while editing.

The tooling is a copy of *Parquet, byte by byte*'s (`snowch/parquet-book`), adapted to a
Python-only book: MyST parses, the repository renders, every number is generated, code is quoted
rather than pasted, and problems are tests. The plan is to extract the shared parts into one
package once both books are stable; until then, a fix to shared tooling is worth making in both.

## Architecture

```
                         THE BOOK (chapters/*.md)
                                   │
                ┌──────────────────┴──────────────────┐
           explanation                           experiment
      {literalinclude} of Python              queries/*.sql, run by
      and SQL; {include} of                   DuckDB and the engine
      generated tables                                │
                └──────────────────┬──────────────────┘
                                   │
       python/query_lab (the engine) ──scan layer──▶ external/parquet-book/python/parquet_lab
                                   │                   (the Parquet book's reader, a submodule)
        ┌──────────────┬───────────┼──────────────┬───────────────────┐
        │              │           │              │                   │
   python/tests   query_lab      query_lab     fixtures/          spikes/duckdb-pyodide
   (engine vs     .figures       .reference    (seeded, written   (the same Python under
    DuckDB)       (every          (DuckDB:      by pyarrow)        Pyodide, in Node and
                  number)         plan, profile)                   Chromium)
```

| Path | What it is |
|---|---|
| `python/query_lab/` | The engine. `operators` (scan, filter, project, pulling Arrow batches), `plans` (a hand-written plan per query, until Part IV's planner), `metrics` (the counters), `reference` (DuckDB), `report` (what panels draw), `figures` (every generated fragment). |
| `exercises/` | The problems: `<slug>.py` stubs, and `tests/test_<slug>.py` graders, skipped unless run with `--problems`. The reader runs them in the chapter's workbench, in the page. |
| `external/parquet-book/` | Git submodule, pinned: the Parquet book. Its `python/parquet_lab` is the engine's scan layer. Never copy it into this repository. |
| `queries/` | Every query a chapter runs, one per file. Pages quote them; figures and tests run them. |
| `fixtures/` | Parquet files written by pyarrow from a seeded generator, each with a manifest (`.json`). |
| `cover.md`, `index.md`, `parts/`, `chapters/`, `appendices/` | The book, in MyST markdown. The cover is the site's `index.html`; the preface is `preface.html`. |
| `public/` | The book's pictures, such as the cover's. |
| `chapters/_generated/` | Fragments written by `python -m query_lab figures`. Never edited by hand. |
| `spikes/` | Experiments that decided something. Each has a README with its findings; tests keep the ones that still matter true. |
| `tools/` | The outline (`outline.py`), the renderer (`render.py`), the highlighter. |
| `scripts/` | Build and check entry points. `ci-check.sh` is what CI runs. |
| `web/` | The site stylesheet, and `web/lab/`: the panels, the problems workbench and Edit and run. A panel draws JSON from `query_lab.report` embedded at build time and can recompute it under Pyodide; the workbench runs a chapter's graders under Pyodide on the reader's answers; Edit and run (`edit.js`) runs the reader's edit of a quoted query, or of a listing of the engine in place of its code (`query_lab.edits`), then a panel's report or the engine's tests. All share one Python worker. |
| `tests/` | Tests of the book, the renderer, and desk-browser parity; `tests/browser/` drives Chromium. |

## Build, run, test

```bash
git submodule update --init   # the Parquet book's reader
make install     # pinned DuckDB and pyarrow, MyST, Pyodide for the parity test
make             # figures + site: _build/html
make serve       # http://localhost:8000
make test        # pytest
make check       # ./scripts/ci-check.sh: exactly what CI runs
```

Always run `make check` before pushing. It runs, in order: ruff, the fixture check, the figures
check, the number check, the MyST parse, the site render, the link check, pytest (the book's
tests, the engine's, and desk-browser parity under Node), and, in headless Chromium, the probe,
every panel, every problems workbench, and the site's chrome served under a base path on a shared
origin.

## How changes land

Work on a branch, open a pull request into `main`, and merge it as soon as CI (the Quality
workflow) is green on its head: the owner does not review each one. Every merge to `main`
deploys the site to GitHub Pages. Nothing is pushed to `main` directly. Before starting new work,
bring the branch level with `main`.

## The invariants

1. **Counters, not time.** Every number the book prints about a run is a counter from
   COUNTERS.md: the same on every machine and in the browser. The book never prints a time.
2. **The reader needs only a browser.** Everything a page asks the reader to run, runs in the
   page: a panel, or a chapter's problems workbench. No page gives a shell command or sends the
   reader to a desk, except one section of the *Running the lab* appendix, *On your own
   machine*, which says how to run the engine and the graders from a clone for a reader who
   wants to; `tests/test_book.py` fails any other page that does.
3. **No number typed into prose.** Counts come from `python -m query_lab figures` fragments
   `{include}`d into the page. `scripts/verify-numbers.py` fails the build otherwise. A definition
   that must be typed takes `% number-ok: <reason>` before its paragraph.
4. **No code pasted into prose.** Python is quoted from `python/` and SQL from `queries/` with
   `{literalinclude}` and `:start-at:` / `:end-before:` text anchors, never `:lines:`. Generated
   output (a plan, a table) comes from an `{include}`. `tests/test_book.py` fails a pasted
   `python`, `sql`, `text` or unlabelled block, and any shell command (invariant 2).
5. **DuckDB is the reference, pinned.** One version at the desk and in the browser, one thread in
   both. Every chapter observes DuckDB first and compares against it last. Upgrading DuckDB is a
   deliberate commit that regenerates every fixture and figure.
6. **The desk and the browser agree.** `tests/test_pyodide.py` runs the same probe natively and
   under Pyodide and requires identical output.
7. **Fixtures are written by a production writer**, from a fixed seed. The engine is tested
   against files it did not write.
8. **No term before its chapter.** Every glossary term names the chapter that introduces it, and
   no earlier chapter uses it. `tests/test_book.py` checks each entry.
9. **Problems are tests.** Stubs the reader fills in, graded by tests that derive the expected
   answer at test time (from DuckDB, a manifest, or a simulator), run by pytest in the page's
   workbench under Pyodide. Never commit a solution.
10. **Deterministic.** Nothing reads a clock or a network to compute a figure. The same commit
   builds the same book.

## Adding things

**A chapter.** Add it to `tools/outline.py` (order, slug, title, part, question, what it builds,
fixtures), regenerate `myst.yml`'s toc to match (the test says how it differs), and run
`make chapter` for the skeleton. Then follow AUTHORING_GUIDE.md. A chapter's number is derived
from its position; its identity is its slug. Never put a number in a slug, label or file name.
Only chapters about to be written go in the outline; PLAN.md holds the draft table of contents.

**A query.** A file in `queries/`, with a comment naming the chapter. Quote it in the page, and
run it in figures and tests through `query_lab.reference.read_query`.

**A fixture.** Add a `Fixture` to `fixtures/generate.py` with a `why` and its `properties`, run
`make fixtures`, and commit the `.parquet`, the `.json` manifest and the regenerated
`fixtures/README.md` together. Add a test of each property to `python/tests/test_fixtures.py`.

**A figure.** Add a `Figure` to `python/query_lab/figures.py` that runs DuckDB or the engine and
returns markdown ending with its conditions line, run `make figures`, and `{include}` it.

**A panel.** Only where a picture beats a table. Add a function to `python/query_lab/report.py`
that returns the JSON to draw, and its name to `EXPERIMENTS` there and in `tools/outline.py`; a
drawing module in `web/lab/` and its mount in `panels.js`; the block's settings to `PANELS` in
`figures.py`; then `make figures` and a ```` ```lab ```` block in the chapter. JavaScript draws;
it never computes a count. `tests/browser/panels.mjs` checks each panel against its JSON and
reruns it under Pyodide; add a reader for any new drawing to it.

**An editable listing.** Follow the `{literalinclude}` of the engine with a ```` ```run ````
block naming a panel's settings or `tests:` in `python/tests/`, and say in the prose one edit to
try. `tests/browser/edits.mjs` runs each as quoted (the build's answer, or every test passing) and
broken. Quoted queries are editable without one.

**A counter.** Change COUNTERS.md first, then `metrics.py`, then every chapter that prints it.

**A glossary term.** An entry in `appendices/glossary.md`, alphabetical, ending with a link to
the chapter that introduces it; that chapter puts the term in bold where it defines it.

## Coding conventions

- **Python:** 3.11 at a desk and whatever Pyodide pins in the page, unchanged. Readable before
  fast: this code is quoted in a book. Dataclasses, exceptions, `match`. `ruff check` and
  `ruff format` clean.
- **JavaScript:** plain ES modules, no framework, no build step. It moves bytes and draws JSON,
  using the colour tokens in `web/book.css` so both themes work.
- **Comments** say why, in full sentences.

## Book-writing conventions

British English, direct, active voice, short sentences, the reader as *you*. No em dashes. No
"In this chapter". No *simply*, *just*, *obviously*, *basically*: `tests/test_book.py` enforces
the list. Every chapter has the ten headings in `tools/outline.CHAPTER_SHAPE`. STYLE.md is the
checklist; run both of its passes over a page before finishing it.

Product names are allowed where the book describes a specific engine's behaviour (DuckDB's plan,
pyarrow's writer). The book is vendor-neutral: Vast DataBase appears once, as a worked example of
pushing work into storage, and the book never recommends a vendor. It credits Andy Grove's work
without following its order or examples; each chapter keeps a list of its primary sources.

## Things that break the build

- Renaming or reformatting a line a `{literalinclude}` anchors on. Search `chapters/` for the text.
- A listing over 80 lines, usually code added between a listing's anchors by a later chapter.
- Changing the engine, a query or a fixture so a generated number moves, without `make figures`.
- Upgrading DuckDB or pyarrow without regenerating fixtures (the generator refuses other versions).
- A new MyST directive or node type without a branch in `tools/render.py`.
- A root-relative URL (`/lab/...`) anywhere in a page: the site is served under a base path.
- A bare browser-storage key for the book's own state. Other books share the origin
  (snowch.github.io); name the key for this book, as `last-read:<base path>` is.
- Moving the submodule without re-running the tests: the scan layer's counters feed figures.
