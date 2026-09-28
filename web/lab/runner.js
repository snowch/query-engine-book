// The page's one Python worker (python-worker.js), shared by every panel and workbench on the
// page. Runs queue: one at a time, in the order they were asked for. The worker starts on the
// first run, never on page load, because Pyodide and its packages are a large download.

let worker = null;
let queue = Promise.resolve();

function run(message, onStatus) {
  const job = queue.then(() => new Promise((resolve, reject) => {
    worker ||= new Worker(new URL("python-worker.js", import.meta.url), { type: "module" });
    worker.onmessage = ({ data }) => {
      if (data.type === "status") return onStatus(data.text);
      if (data.type === "result") resolve(data.json);
      else reject(new Error(data.message));
    };
    worker.onerror = (e) => reject(new Error(e.message || "the Python worker failed"));
    worker.postMessage(message);
  }));
  queue = job.catch(() => {});
  return job;
}

/**
 * Run the report a panel's `config` names. Resolves with the report's JSON text, serialised as the
 * build serialised it, so the two can be compared.
 */
export function runReport(config, onStatus = () => {}) {
  return run({ kind: "report", config }, onStatus);
}

/**
 * Run a chapter's graders on `source`, the reader's edit of the chapter's stubs. Resolves with
 * JSON text: {exit, tests: [{name, outcome, message}], output}.
 */
export function runProblems(chapter, source, onStatus = () => {}) {
  return run({ kind: "problems", chapter, source }, onStatus);
}
