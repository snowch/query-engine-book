// The probe under Pyodide in Node: the browser's Python, DuckDB and pyarrow, without a browser.
// Pyodide comes from node_modules (package.json pins it); its packages come from its CDN.
//
// stdout carries the probe's JSON and nothing else, because a test compares it byte for byte.
// Pyodide reports package downloads while it loads (more of them on a machine that has not cached
// its wheels yet), on its own output and on the console. Both go to stderr until the packages
// are in; then Python's output goes to stdout, through the original stream.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { loadPyodide } from "pyodide";
import { ROOT, RUN, probeFiles } from "./files.mjs";

const out = process.stdout.write.bind(process.stdout);
process.stdout.write = process.stderr.write.bind(process.stderr);

const toStderr = { batched: (s) => process.stderr.write(`${s}\n`) };
const pyodide = await loadPyodide({ stdout: toStderr.batched, stderr: toStderr.batched });
await pyodide.loadPackage(["duckdb", "pyarrow"], { messageCallback: () => {} });
pyodide.setStdout({ batched: (s) => out(`${s}\n`) });
pyodide.setStderr(toStderr);
for (const file of probeFiles()) {
  const target = `/book/${file}`;
  pyodide.FS.mkdirTree(dirname(target));
  pyodide.FS.writeFile(target, readFileSync(join(ROOT, file)));
}
pyodide.runPython(RUN);
