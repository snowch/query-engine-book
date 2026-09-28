#!/usr/bin/env bash
# Exactly what CI runs. Run it before pushing: `make check`.
#
# CI invokes this same script, so a laptop and CI cannot drift. Each stage says what it protects,
# because a check nobody understands is a check somebody eventually deletes.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="python:external/parquet-book/python"

PY_PATHS=(python fixtures tools scripts tests spikes)

echo "== the scan layer is present =="
# The Parquet book's reader is a submodule. Without it nothing below can import the scan.
if [ ! -f external/parquet-book/python/parquet_lab/scan.py ]; then
  echo "ERROR: external/parquet-book is empty; run \`git submodule update --init\`" >&2
  exit 1
fi

echo "== Python: lint and format =="
python3 -m ruff check "${PY_PATHS[@]}"
python3 -m ruff format --check "${PY_PATHS[@]}"

echo "== the fixtures are what the generator writes =="
# The fixtures are committed bytes. This regenerates them with the pinned pyarrow and DuckDB and
# fails on any difference, so the manifests, the files and the appendix cannot disagree.
python3 fixtures/generate.py --check

echo "== the generated fragments are what the engines compute =="
# Every number a chapter prints comes from these. A change to the engine, a query, a fixture or
# DuckDB that moves a number fails here until `make figures` is run and the result committed.
python3 -m query_lab figures --check

echo "== no measured number is typed into prose =="
python3 scripts/verify-numbers.py

echo "== MyST parses every page and resolves every reference =="
./scripts/parse-book.sh

echo "== the site renders =="
# The renderer raises on a node type it does not handle, so rendering every page on every push is
# what stops new markup from silently disappearing.
python3 scripts/build-site.py --out _build/html

echo "== every link in the built site resolves =="
python3 scripts/check-built-links.py _build/html

echo "== the book's tests, the engine's, and desk-browser parity under Node =="
python3 -m pytest -q

echo "== the DuckDB probe and the panels, in a headless browser =="
# Needs Playwright and a Chromium. CI installs both; locally the check runs if they are present.
# The panels check draws every panel from the build's JSON, then runs its report under Pyodide
# and requires the same answer, drawn the same way.
if node -e "require.resolve('playwright')" >/dev/null 2>&1 \
   || [ -d "$(npm root -g 2>/dev/null)/playwright" ]; then
  ./scripts/browser-probe.sh
  node tests/browser/panels.mjs _build/html
elif [ -n "${CI:-}" ]; then
  echo "ERROR: Playwright is not installed, and CI must not skip the browser check." >&2
  exit 1
else
  echo "  Playwright not installed; skipping (npm install -g playwright && npx playwright install chromium)"
fi

echo
echo "All checks passed."
