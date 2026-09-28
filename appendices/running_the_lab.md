---
title: Running the lab
---

(running-the-lab)=
# Running the lab

## At a desk

You need Python 3.11 or later and Git. From a fresh clone:

```bash
git clone --recurse-submodules https://github.com/snowch/query-engine-book
cd query-engine-book
make install
make
make serve
```

`make install` installs the pinned DuckDB and pyarrow, and the pinned MyST the site is parsed
with. `make` generates the figures and builds the site into `_build/html`, and `make serve`
serves it locally. `make check` runs everything CI runs.

The engine's scan layer is the Parquet reader from *Parquet, byte by byte*. It is a Git
submodule in `external/parquet-book`, so clone with `--recurse-submodules`, or run
`git submodule update --init` in a clone you already have.

## In your browser

The pages will run the engine's Python in your browser, under Pyodide, with the same DuckDB and
pyarrow versions a desk uses. That part of the lab is being built. The first run downloads
Python, DuckDB and pyarrow, which is a large download; your browser keeps them after that.

## Versions

The book pins DuckDB and pyarrow to the versions the browser's Python ships, so a plan printed in
the book is the plan you see in the page and at a desk. `requirements.txt` holds the pins, and
`spikes/duckdb-pyodide/README.md` explains the choice.
