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

## Predict, then reveal

A panel is the chapter's one exhibit of a run, not a second copy of a table. Two findings decided
that: showing the same numbers twice makes a reader reconcile them instead of thinking (the
redundancy effect in multimedia-learning research), and a prediction the reader commits to before
seeing the answer is what makes the gap memorable (predict, observe, explain).

So the plan panel asks first. For the book's query it opens with the planner's estimates, which
`EXPLAIN` printed before the query ran, a box per operator for the reader's prediction, and every
measurement hidden: the bars, the rows in and out, the rows on the links and the result. Before
the reveal, bars are scaled to the estimates alone, so a bar's length gives nothing away. After
it, each operator has three bars on one scale: the reader's prediction, the estimate and the
measurement. Predictions and the reveal are kept in the browser's storage; *Predict again* clears
them. A reader can reveal without predicting.

Without JavaScript the panel says it needs JavaScript, and nothing else. A static copy of the
numbers would be a second exhibit to keep in step with the first, for few readers.

## Editing the query

A panel whose report ran a query has an editor under it (*Edit the query*, closed until used).
The reader's text goes to the same report as `sql`, and the panel redraws from what comes back,
with the first rows of the result under the plan. An edit:

- **is never compared with the build**, because the build never ran it; the status line says it
  is the reader's query instead;
- **is kept in the browser's storage**, per panel, and *Reset to the book's query* drops it;
- **fails politely**: DuckDB's error message (its last line, without the Python traceback) goes
  in the status line, and the last drawing stays.

`tests/browser/panels.mjs` edits the query, requires the drawing to match what
`python -m query_lab report plan <query> --sql <text>` prints at a desk for the same text, runs a
broken query, and resets. An operator DuckDB gives no estimate for (`ORDER_BY`) reports `null`,
and the panel draws *none*, never a zero the planner did not claim.

## What the checks hold

| Check | What it requires |
|---|---|
| `figures --check` | Every panel's committed JSON is what `query_lab.report` computes now. |
| `python/tests/test_report.py` | The plan report matches DuckDB's profile; it holds no timings; every panel in `figures.PANELS` is generated; an edited query runs and says so. |
| `tests/test_render.py` | A `lab` block carries its JSON; a missing query or panel fails the build. |
| `tests/test_book.py` | Every experiment has a mount and a report function. |
| `tests/browser/panels.mjs` | In Chromium: the panel asks before it answers and hides every measurement; typed predictions and the reveal draw the build's numbers beside the predictions and survive a reload; *Run it in your browser* gives the build's answer; an edited query draws the desk's answer for it; a broken one reports DuckDB's error; reset and *Predict again* work; without JavaScript, the panel says it needs it. |

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

- **Panels of the book's own engine.** When ch01's operators exist, a report can run the engine's
  plan and DuckDB's side by side in one JSON, and the same panel can draw both.
