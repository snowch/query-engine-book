---
title: Running the lab
---

(running-the-lab)=
# Running the lab

Reading the book requires no code or execution. Worked results, plans and comparisons are
already visible on each page, even without JavaScript. This appendix describes the optional
experiments and implementation route; there is nothing to install to use them in your browser.

## Panels

Open **Explore the saved plans** to switch between plans the book computed when it was built.
Click **Run the book's query in your browser** to recompute the original query.

For other panels, open **Predict and reveal the experiment** below the worked result. Enter
your predictions and select **Reveal the measurement**. **Run it in your browser** reruns the
original experiment after the reveal. The panel says whether the counts match the worked result.

If the panel offers **Edit the query**, change it there and click **Run your query in your
browser**. Use **Reset to the book's query** to bring back the original, then **Recover saved
draft** when you want your edit again.

## Edit and run

Open an **Optional: read or edit** section and click **Edit and run** to open its editor.
**Run the query** shows your SQL query's plan and first result rows. **Run the listing** runs
your Python code and shows its output, counters or test results. A failed run leaves any
previous result visible.

Press Tab to move out of the editor, or Ctrl+Enter to run from it. **Reset to the book's code**
opens the starter. **Recover saved draft** brings back the previous edit. The page saves drafts
in this browser when storage is available. If saving fails, **Download editor text** keeps a
copy of the exact text in the editor.

## Timings

Open **Optional: measure timings in your browser** to compare cases: a top-k against a full sort, say. Nothing is timed until you
press **Time it in your browser**; then each case runs, several times if it is quick, and shows
how long it took and how it compares with the fastest. A time is your machine's, now: it moves
from run to run, and Python and DuckDB run slower in a browser than at a desk, so compare the
cases with each other. Nothing else on the page runs while the cases are timed.

## Problems

Each chapter's understanding check needs no code. For coding practice, open
**Optional: write code and run the practice tests** under Problems. Write your answers and click
**Run the practice tests**. The checks report on the answers you submitted. Running the tests
again checks any later edits. **Reset to the stubs** brings back the starter code. **Recover
saved draft** brings back your answers.

## The first run

The first run downloads the browser's Python runtime, called Pyodide. Each experiment also
loads the libraries it needs, such as DuckDB or pyarrow. The first run can take longer than a
later run in the same browser. Reading the book leaves those downloads until you select Run.

## Versions

The browser and build use the same pinned versions of DuckDB and pyarrow. An original rerun
checks the displayed counters against the build's example. An edited run reports its own result.

## On your own machine

The book never needs this. If you would rather edit the engine in your own editor, or run the
graders from a terminal, everything the page runs also runs from a clone of the repository. You
need Python 3.11 or later, Git, and Node for the site.

```bash
git clone --recurse-submodules https://github.com/snowch/query-engine-book
cd query-engine-book
make install
```

`make install` installs the pinned DuckDB and pyarrow, the pinned MyST, and fetches the Parquet
book's reader, which is the engine's scan layer, into `external/parquet-book`. The commands
below run from the repository's root, with the engine and the reader on Python's path:

```bash
export PYTHONPATH=python:external/parquet-book/python
python3 -m query_lab observe queries/returned_unit_price.sql   # DuckDB's plan and profile
python3 -m query_lab run queries/returned_unit_price.sql       # your engine's plan and counters
python3 -m query_lab time top_k                                # a chapter's timed cases, timed here
```

A chapter's problems are stubs in `exercises/<chapter>.py`, and their graders are in
`exercises/tests/`. The graders are skipped unless you ask for them:

```bash
python3 -m pytest exercises/tests/test_the_plan_is_the_map.py --problems
python3 -m pytest exercises/tests/test_the_plan_is_the_map.py --problems -k problem_1_1
```

Answers you write here and answers you write in the page's workbench are separate: the page
keeps its own in your browser.

`make` builds the figures and the site into `_build/html`, `make serve` serves it, and
`make check` runs everything the book's CI runs.
