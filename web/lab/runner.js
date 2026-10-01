// The page's one Python worker (python-worker.js), shared by every panel and workbench on the
// page. Runs queue: one at a time, in the order they were asked for. The worker starts on the
// first run, never on page load, because Pyodide and its packages are a large download.

let worker = null;
let queue = Promise.resolve();

/** How long an edit may run once it starts, before the page stops it: code a reader wrote may
 * never finish, and the worker would never run anything else. */
export const EDIT_LIMIT_MS = 180_000;

function run(message, onStatus, limit = 0) {
  const job = queue.then(() => new Promise((resolve, reject) => {
    worker ||= new Worker(new URL("python-worker.js", import.meta.url), { type: "module" });
    let timer = null;
    const done = (fn) => (value) => { clearTimeout(timer); fn(value); };
    worker.onmessage = ({ data }) => {
      if (data.type === "status") {
        // The clock starts when the code starts, not while Pyodide downloads.
        if (limit && !timer && data.text.startsWith("Running")) {
          timer = setTimeout(() => {
            worker.terminate();
            worker = null;
            reject(new Error(`it ran for ${limit / 60_000} minutes without finishing, so the page stopped it`));
          }, limit);
        }
        return onStatus(data.text);
      }
      if (data.type === "result") done(resolve)(data.json);
      else done(reject)(new Error(data.message));
    };
    worker.onerror = (e) => done(reject)(new Error(e.message || "the Python worker failed"));
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

/**
 * Run the reader's `text`, their edit of `listing` from `file`, in place of the engine's code,
 * then `then`: {report: config} or {tests: {tests, select}}. Resolves with JSON text:
 * {report}, {tests, exit, output}, or {error}. An edit still running after EDIT_LIMIT_MS is stopped,
 * and the worker with it; the next run starts a fresh one.
 */
export function runEdit(file, listing, text, then, onStatus = () => {}) {
  return run({ kind: "edit", file, listing, text, then }, onStatus, EDIT_LIMIT_MS);
}

/**
 * Time case `index` of the timing `of` (query_lab.timing), in this browser. Resolves with JSON
 * text: {seconds, runs, profile, where}. The worker runs one thing at a time, so nothing else on
 * the page runs while a case is timed.
 */
export function runTiming(of, index, status, onStatus = () => {}) {
  return run({ kind: "timing", of, index, status }, onStatus);
}
