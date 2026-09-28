"""The desk and the browser run the same engine: the spike in PLAN.md (Phase 0), kept as a test.

``spikes/duckdb-pyodide/probe.py`` prints DuckDB's results, plans and counters for every query in
``queries/``, and what the Parquet book's scan fetched. This test runs it natively and under
Pyodide in Node, and requires the same document byte for byte. If a DuckDB or Pyodide upgrade
changes a plan or a counter in one place and not the other, this is where it shows.

It needs Node and ``npm install`` (Pyodide from package.json), and the network, for Pyodide's
packages; without them it is skipped at a desk and fails in CI. ``scripts/ci-check.sh`` runs the
same probe in Chromium too.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "spikes" / "duckdb-pyodide"


def desk() -> str:
    return subprocess.run(
        [sys.executable, str(PROBE / "probe.py")], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def test_the_browsers_python_gives_the_desks_answers():
    if not shutil.which("node") or not (ROOT / "node_modules" / "pyodide").is_dir():
        if os.environ.get("CI"):
            pytest.fail("CI must run the Pyodide parity test: npm install")
        pytest.skip("needs Node and `npm install` for Pyodide")
    node = subprocess.run(
        ["node", str(PROBE / "node.mjs")], cwd=ROOT, capture_output=True, text=True, timeout=600
    )
    assert node.returncode == 0, node.stderr[-2000:]
    assert node.stdout == desk()
