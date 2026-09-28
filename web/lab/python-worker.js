// The page's Python, under Pyodide: a panel's report, or a chapter's problems and their graders.
//
// A report is query_lab.report.run, the function the build ran to draw the panel. Problems are
// the chapter's graders, run by pytest exactly as the repository runs them, on the reader's edit of
// the chapter's stubs. Pyodide and each package are fetched on first use only: a plan's report
// needs DuckDB alone; a gather's also needs pyarrow, for the engine; the graders need both, and
// pytest.

import { ROOT, startPyodide, writeBook } from "./pyodide.js";

// Queries name their fixtures relative to the repository's root, as the build runs them.
const RUN = `
import io, json, os, sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

os.chdir("${ROOT}")
sys.dont_write_bytecode = True
for extra in ("${ROOT}/python", "${ROOT}/exercises"):
    if extra not in sys.path:
        sys.path.insert(0, extra)


def run_report(config_json):
    from query_lab import report

    report_json = report.run(Path("${ROOT}"), json.loads(config_json))
    # Serialised as the renderer serialises the build's JSON, so the page can compare them.
    return json.dumps(report_json, separators=(",", ":"))


class Collect:
    """Each test's outcome, as pytest reports it."""

    def __init__(self):
        self.tests = []

    def pytest_runtest_logreport(self, report):
        # A test's call decides it; a setup that fails or skips decides it before any call.
        if report.when != "call" and report.outcome == "passed":
            return
        message = ""
        if report.failed:
            crash = getattr(report.longrepr, "reprcrash", None)
            message = crash.message if crash else report.longreprtext.strip().splitlines()[-1]
        elif report.skipped and isinstance(report.longrepr, tuple):
            message = report.longrepr[2]
        self.tests.append({"name": report.nodeid.split("::")[-1], "outcome": report.outcome, "message": message})


def run_problems(chapter, source):
    import pytest

    with open(f"${ROOT}/exercises/{chapter}.py", "w") as f:
        f.write(source)
    # Forget the last run's stub and graders, so this run imports what is on disk now.
    for name in [n for n in sys.modules if n in (chapter, f"test_{chapter}") or n.startswith("conftest")]:
        del sys.modules[name]
    collect = Collect()
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(out):
        code = int(pytest.main(
            # The graders only: the scaffolding beside them checks the stubs are unsolved, which a
            # reader's answer is not.
            [f"exercises/tests/test_{chapter}.py", "--problems", "-k", "problem", "-q", "--color=no",
             "-p", "no:cacheprovider"],
            plugins=[collect],
        ))
    return json.dumps({"exit": code, "tests": collect.tests, "output": out.getvalue()})
`;

let ready = null;
const loaded = new Set();

/** The packages each experiment's report needs, beyond Pyodide itself. */
const NEEDS = { plan: ["duckdb"], gather: ["duckdb", "pyarrow"] };

async function setup() {
  postMessage({ type: "status", text: "Loading Python into your browser (a large download, the first time only)…" });
  const pyodide = await startPyodide();
  postMessage({ type: "status", text: "Fetching the engine, the problems, the queries and the fixtures…" });
  await writeBook(pyodide, import.meta.url);
  pyodide.runPython(RUN);
  return pyodide;
}

/** Load the packages a run needs that are not loaded yet, saying so, since they are large. */
async function need(pyodide, packages) {
  const missing = packages.filter((p) => !loaded.has(p));
  if (!missing.length) return;
  postMessage({ type: "status", text: `Loading ${missing.join(", ")} into your browser (the first time only)…` });
  await pyodide.loadPackage(missing, { messageCallback: () => {} });
  missing.forEach((p) => loaded.add(p));
}

onmessage = async ({ data }) => {
  try {
    ready ||= setup();
    const pyodide = await ready;
    if (data.kind === "report") {
      await need(pyodide, NEEDS[data.config.experiment] || ["duckdb", "pyarrow"]);
      postMessage({ type: "status", text: "Running…" });
      postMessage({ type: "result", json: pyodide.globals.get("run_report")(JSON.stringify(data.config)) });
    } else if (data.kind === "problems") {
      await need(pyodide, ["duckdb", "pyarrow", "pytest"]);
      postMessage({ type: "status", text: "Running the graders…" });
      postMessage({ type: "result", json: pyodide.globals.get("run_problems")(data.chapter, data.source) });
    } else {
      throw new Error(`no such run: ${data.kind}`);
    }
  } catch (error) {
    // A run that failed to start (a network error, say) is tried afresh next time.
    if (!(await ready.then(() => true, () => false))) ready = null;
    postMessage({ type: "error", message: String(error.message || error) });
  }
};
