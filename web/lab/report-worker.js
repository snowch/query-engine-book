// Runs a panel's report under Pyodide: query_lab.report.run, the function the build ran at a desk.
//
// Only DuckDB is loaded, not pyarrow: the plan panel needs nothing else, and DuckDB alone is a
// fraction of the download pyarrow and its dependencies would add. A panel that needs pyarrow
// will load it on its first run, the way Pyodide loads any package.

import { ROOT, startPyodide, writeBook } from "./pyodide.js";

// Queries name their fixtures relative to the repository's root, as a desk runs them.
const RUN = `
import json, os
from pathlib import Path
from query_lab import report

os.chdir("${ROOT}")

def run_report(config_json):
    report_json = report.run(Path("${ROOT}"), json.loads(config_json))
    # Serialised as the renderer serialises the build's JSON, so the page can compare strings.
    return json.dumps(report_json, separators=(",", ":"))
`;

let ready = null;

async function setup() {
  postMessage({ type: "status", text: "Loading Python and DuckDB into your browser (a large download, the first time only)…" });
  const pyodide = await startPyodide();
  await pyodide.loadPackage("duckdb", { messageCallback: () => {} });
  postMessage({ type: "status", text: "Fetching the engine, the queries and the fixtures…" });
  await writeBook(pyodide, import.meta.url);
  pyodide.runPython(RUN);
  return pyodide.globals.get("run_report");
}

onmessage = async ({ data }) => {
  try {
    ready ||= setup();
    const run = await ready;
    postMessage({ type: "status", text: "Running…" });
    postMessage({ type: "result", json: run(JSON.stringify(data.config)) });
  } catch (error) {
    // A run that failed to start (a network error, say) is tried afresh next time.
    if (!(await ready.then(() => true, () => false))) ready = null;
    postMessage({ type: "error", message: String(error.message || error) });
  }
};
