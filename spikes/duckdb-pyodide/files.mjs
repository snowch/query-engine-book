// The repository files the probe needs, as Pyodide's file system will hold them: the book's
// engine, the Parquet book's reader from the submodule, the fixtures, the queries and the probe.
// Shared by node.mjs (which reads them from disk) and browser.mjs (which serves them).

import { readdirSync } from "node:fs";
import { join } from "node:path";

export const ROOT = new URL("../../", import.meta.url).pathname;

const list = (dir, suffix) =>
  readdirSync(join(ROOT, dir)).filter((f) => f.endsWith(suffix)).map((f) => `${dir}/${f}`);

/** Every file of every table of many files among the fixtures: a directory with its metadata. */
const tables = () => readdirSync(join(ROOT, "fixtures"), { withFileTypes: true })
  .filter((d) => d.isDirectory() && readdirSync(join(ROOT, "fixtures", d.name)).includes("metadata.json"))
  .flatMap((d) => readdirSync(join(ROOT, "fixtures", d.name), { recursive: true })
    .filter((f) => f.endsWith(".parquet") || f === "metadata.json")
    .map((f) => `fixtures/${d.name}/${f}`));

export function probeFiles() {
  return [
    ...list("python/query_lab", ".py"),
    ...list("external/parquet-book/python/parquet_lab", ".py"),
    ...list("fixtures", ".parquet"),
    ...tables(),
    ...list("queries", ".sql"),
    "spikes/duckdb-pyodide/probe.py",
  ];
}

// Run after the files are in place under /book: the same entry point as a desk.
export const RUN = `
import os, runpy, sys
os.chdir("/book")
sys.argv = ["probe.py"]
runpy.run_path("spikes/duckdb-pyodide/probe.py", run_name="__main__")
`;
