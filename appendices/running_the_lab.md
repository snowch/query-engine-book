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

For other panels, open **Optional: predict, change and run the experiment** beneath the worked
result. **Run it in your browser** recomputes the original experiment. The panel says whether
the new counts match the worked result.

If the panel offers **Edit the query**, change it there and click **Run your query in your
browser**. Use **Reset to the book's query** to bring back the original, then **Recover saved
draft** when you want your edit again.

## Edit and run

Open an **Optional: read or edit** section and click **Edit and run** to open its editor.
**Run the query** shows your SQL query's plan and first result rows. **Run the listing** runs
your Python code and shows its output, counters or test results. A failed run leaves any
previous result visible.

Press Tab to move out of the editor or Ctrl+Enter to run from it. Your edit stays in this
browser. Click **Reset to the book's code** to open the starter again. **Recover saved draft**
brings back your edit, including after you reload.

## Timings

Open **Optional: measure timings in your browser** to compare cases: a top-k against a full sort, say. Nothing is timed until you
press **Time it in your browser**; then each case runs, several times if it is quick, and shows
how long it took and how it compares with the fastest. A time is your machine's, now: it moves
from run to run, and Python and DuckDB run slower in a browser than at a desk, so compare the
cases with each other. Nothing else on the page runs while the cases are timed.

## Problems

Each chapter's understanding check needs no code. For coding practice, open
**Optional: write code and run the practice tests** under Problems. Write your answers and click
**Run the graders**. The book runs the practice checks in your browser and reports which passed.
**Reset to the stubs** brings back the starter code. **Recover saved draft** brings back your
answers.

## The first run

The first run downloads Python, DuckDB and, for the problems, pyarrow and pytest. That is a large
download, and your browser keeps it afterwards, so later runs start quickly. Each download
happens only when something first needs it: reading the book does not download the Python runtime.

## Versions

The book pins DuckDB and pyarrow to the versions the browser's Python ships, so a plan printed in
the book is the plan your browser makes when you run it.

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
