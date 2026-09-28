#!/usr/bin/env bash
# The DuckDB-in-Pyodide probe in headless Chromium, compared byte for byte with the desk.
#
# tests/test_pyodide.py compares the desk with Pyodide under Node. This runs the same probe in a
# real browser, so a difference that only a browser shows (a fetch, a module import, WebAssembly
# limits) fails the build too. Needs Playwright and a Chromium.
set -euo pipefail
cd "$(dirname "$0")/.."

desk=$(mktemp)
browser=$(mktemp)
trap 'rm -f "$desk" "$browser"' EXIT
python3 spikes/duckdb-pyodide/probe.py > "$desk"
node spikes/duckdb-pyodide/browser.mjs > "$browser"
if ! cmp -s "$desk" "$browser"; then
  echo "ERROR: the probe printed different results in Chromium and at the desk:" >&2
  diff <(python3 -m json.tool "$desk") <(python3 -m json.tool "$browser") >&2 || true
  exit 1
fi
echo "  Chromium and the desk agree"
