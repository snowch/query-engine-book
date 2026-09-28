---
title: Running the lab
---

(running-the-lab)=
# Running the lab

Everything the book asks you to run, runs in this page, in your browser. There is nothing to
install.

## Panels

A panel draws what the engine computed when the book was built, so it appears at once with
nothing to download. Its **Run it in your browser** button runs the same code again in your
browser, under Pyodide, and says whether your browser got the same answer as the build. A panel
that shows a query lets you edit the query and run your own.

## Problems

Each chapter's problems open with a workbench. Write your answers in it and press **Run the
graders**: they are the book's own tests, run by pytest in your browser, and they report each
check as it passed or failed. Your answers stay in this browser, and **Reset to the stubs**
starts again.

## The first run

The first run downloads Python, DuckDB and, for the problems, pyarrow and pytest. That is a large
download, and your browser keeps it afterwards, so later runs start quickly. Each download
happens only when something first needs it: reading the book downloads nothing.

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
