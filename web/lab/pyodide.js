// Pyodide, and the book's Python files inside it, for the worker that runs the panels' reports.
//
// Pyodide is CPython compiled to WebAssembly, fetched from a pinned release on a public CDN only
// when a reader runs something. The version is the one requirements.txt matches: its DuckDB is the
// DuckDB the book was built with (spikes/duckdb-pyodide/README.md). The book's own files come
// from this site and go into Pyodide's file system in the repository's layout.

export const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/";

/** Where the repository's files go in Pyodide's file system. */
export const ROOT = "/book";

export async function startPyodide() {
  const { loadPyodide } = await import(`${PYODIDE}pyodide.mjs`);
  return loadPyodide({ indexURL: PYODIDE });
}

async function fetchOk(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`could not fetch ${url}: ${r.status}`);
  return r;
}

/** Write `bytes` to `path`, making its directories. */
function writeFile(pyodide, path, bytes) {
  pyodide.FS.mkdirTree(path.slice(0, path.lastIndexOf("/")));
  pyodide.FS.writeFile(path, bytes);
}

/**
 * Lay out what the build listed in py/package.json (from `base`, a URL in web/lab): the Python
 * packages and the queries under py/, and the fixtures beside the lab.
 */
export async function writeBook(pyodide, base) {
  const list = await (await fetchOk(new URL("py/package.json", base))).json();
  const files = [
    ...Object.entries(list.packages).flatMap(([pkg, modules]) =>
      modules.map((m) => [`py/${pkg}/${m}`, `${ROOT}/python/${pkg}/${m}`])),
    ...list.queries.map((q) => [`py/queries/${q}`, `${ROOT}/queries/${q}`]),
    ...list.fixtures.map((f) => [`../fixtures/${f}`, `${ROOT}/fixtures/${f}`]),
  ];
  const bodies = await Promise.all(files.map(async ([from]) =>
    new Uint8Array(await (await fetchOk(new URL(from, base))).arrayBuffer())));
  files.forEach(([, to], i) => writeFile(pyodide, to, bodies[i]));
  pyodide.runPython(`
import sys
if "${ROOT}/python" not in sys.path:
    sys.path.insert(0, "${ROOT}/python")
`);
}
