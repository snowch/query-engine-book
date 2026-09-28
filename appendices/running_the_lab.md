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
