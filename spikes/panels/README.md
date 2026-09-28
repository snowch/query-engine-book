# Spike: panels without Rust

PLAN.md, Phase 0, asks whether a panel can be drawn without Rust, from Python or JavaScript. In
the Parquet book a panel is a picture of JSON the Rust reader computes, compiled to WebAssembly.
This book has no Rust, so something else must compute the JSON, and the invariant must survive:
a panel draws what the implementation computed, never a scripted animation.

**Answer: Python computes, JavaScript draws, and the build draws first.** The first panel, the
plan panel in ch01, is built this way and checked in CI.

## How a panel works

```
queries/*.sql ─▶ query_lab.report.<experiment>(root, **settings) ─▶ JSON
                        │                                         │
        at build time: python -m query_lab figures      in the page, on request:
        writes chapters/_generated/panel-*.json,        web/lab/report-worker.js runs the
        the renderer embeds it in the page              same function under Pyodide
                        │                                         │
                        └──────────▶ web/lab/<experiment>.js draws it ◀──────────┘
```

1. **One Python function per experiment**, in `python/query_lab/report.py`, returns the JSON
   the panel draws. For `plan`: DuckDB's operators as a tree, each with the planner's estimate
   and the profile's rows in and out.
2. **The build runs it.** `python -m query_lab figures` writes each panel's JSON beside the
   other generated fragments, and `figures --check` fails if it is stale, like any figure.
3. **The page draws it at once.** The renderer embeds the JSON in the lab block's mount point.
   The panel draws with nothing downloaded: no Pyodide, no DuckDB.
4. **The reader can run it again.** *Run it in your browser* starts a worker that loads Pyodide
   and DuckDB, lays the engine, the queries and the fixtures out in its file system, and calls
   the same function. The panel redraws from the result and says whether it is the build's
   answer.
5. **JavaScript only draws.** `web/lab/plan.js` turns fields into boxes and bars. The one
   computation in the page is the equality check between the two answers.

## Why the build draws first

The first run in a browser is a large download (see the DuckDB spike). Drawing from the build's
JSON means a reader who only reads never pays it, and a reader on a phone sees the panel
instantly. The live run is there to show that the numbers are not a picture someone made: the
reader's own browser recomputes them.

The worker loads DuckDB alone, not pyarrow. For the plan panel that is the Pyodide runtime,
its standard library and the DuckDB wheel: roughly half of what DuckDB with pyarrow and its
dependencies would be. A panel that needs pyarrow loads it on first use.

## What the checks hold

| Check | What it requires |
|---|---|
| `figures --check` | Every panel's committed JSON is what `query_lab.report` computes now. |
| `python/tests/test_report.py` | The plan report matches DuckDB's profile; it holds no timings; every panel in `figures.PANELS` is generated. |
| `tests/test_render.py` | A `lab` block carries its JSON; a missing query or panel fails the build. |
| `tests/test_book.py` | Every experiment has a mount in `lab.js` and a report function. |
| `tests/browser/panels.mjs` | In Chromium, every number a panel draws is a field of the build's JSON; after *Run it in your browser*, the page says the answers agree and draws the same numbers. |

## Findings

- **Chromium runs the plan report under Pyodide and gets the build's answer**: the same JSON once
  parsed, so the same operators, estimates and row counts. The whole check, including loading Pyodide
  and DuckDB from the CDN, took under ten seconds here.
- **Queries are relative to the repository's root**, so the worker changes into the root of its
  file system before running a report, as a desk does.
- **The browser tests need no server.** They answer the site's requests from disk through the
  browser context's route handler (`tests/browser/chromium.mjs`), which also answers the page's
  worker. A local server would not work behind this sandbox's proxy: Playwright sends even
  loopback requests through a configured proxy.
- **The panel reads well at phone width and in both themes** with the book's colour tokens.
  Long plan details (an expression, a filter) wrap inside the operator's box.

## Open

- **Where a panel sits in a chapter.** ch01 keeps the generated profile table, which works
  without JavaScript and reads well in print, and adds the panel after it. Whether a panel should
  replace a table is a writing decision for the pilot review.
- **Editing the query in the page.** The worker can run any query in `queries/`; letting a
  reader edit one and redraw is a small step from here, and the Parquet book's workbench shows
  the editor half.
- **Panels of the book's own engine.** When ch01's operators exist, a report can run the engine's
  plan and DuckDB's side by side in one JSON, and the same panel can draw both.
