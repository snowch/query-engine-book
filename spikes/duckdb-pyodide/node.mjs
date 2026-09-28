// The probe under Pyodide in Node: the browser's Python, DuckDB and pyarrow, without a browser.
// Pyodide comes from node_modules (package.json pins it); its packages come from its CDN.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { loadPyodide } from "pyodide";
import { ROOT, RUN, probeFiles } from "./files.mjs";

// Pyodide reports package downloads on console.log; stdout is kept for the probe's JSON.
const log = console.log;
console.log = console.error;
const pyodide = await loadPyodide();
await pyodide.loadPackage(["duckdb", "pyarrow"], { messageCallback: () => {} });
console.log = log;
pyodide.setStdout({ batched: (s) => process.stdout.write(`${s}\n`) });
pyodide.setStderr({ batched: (s) => process.stderr.write(`${s}\n`) });
for (const file of probeFiles()) {
  const target = `/book/${file}`;
  pyodide.FS.mkdirTree(dirname(target));
  pyodide.FS.writeFile(target, readFileSync(join(ROOT, file)));
}
pyodide.runPython(RUN);
