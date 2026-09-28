// The page's one Python worker (report-worker.js), shared by every panel on the page. Runs queue:
// one at a time, in the order they were asked for. The worker starts on the first run, never on
// page load, because Pyodide and DuckDB are a large download.

let worker = null;
let queue = Promise.resolve();

/**
 * Run the report a panel's `config` names under Pyodide. Resolves with the report's JSON text,
 * serialised exactly as the build serialised it, so the two can be compared as strings.
 */
export function runReport(config, onStatus = () => {}) {
  const job = queue.then(() => new Promise((resolve, reject) => {
    worker ||= new Worker(new URL("report-worker.js", import.meta.url), { type: "module" });
    worker.onmessage = ({ data }) => {
      if (data.type === "status") return onStatus(data.text);
      if (data.type === "result") resolve(data.json);
      else reject(new Error(data.message));
    };
    worker.onerror = (e) => reject(new Error(e.message || "the Python worker failed"));
    worker.postMessage({ config });
  }));
  queue = job.catch(() => {});
  return job;
}
