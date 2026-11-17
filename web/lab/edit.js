// Edit and run: the reader changes a quoted listing and runs it in the page.
//
// Two kinds of listing can be edited. Every quoted query: the reader's text runs through the plan
// panel's report, under DuckDB in the page's Python worker, and draws as the plan panel draws an
// edited query. And a listing of the engine that the chapter follows with a `run` block: the
// reader's text runs in place of the engine's own code (query_lab.edits), then the page runs what
// the block names, a panel's report or some of the engine's tests, and undoes the edit.
//
// The page draws what Python returned and compares it with the build's answer when there is one;
// it computes nothing itself. An edit is kept in the browser's storage under a key named for this
// book, since other books share the origin, and never touches the numbers the chapter prints.

import { bindDraft, bookPath, store } from "./drafts.js";
import { colour } from "./highlight.js";
import { EXPERIMENTS } from "./panels.js";
import { runEdit, runReport } from "./runner.js";

// A panel drawn from an edit shows its measurements at once: there is nothing left to predict.
const revealed = {
  get(key) { return key.endsWith(":predict") ? JSON.stringify({ predictions: {}, revealed: true }) : null; },
  set() {},
  drop() {},
};

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

function lastLine(error) {
  const lines = String(error.message || error).split("\n").map((l) => l.trim()).filter(Boolean);
  return lines[lines.length - 1] || "unknown error";
}

/** The engine's tests, as pytest reported them on the reader's edit. */
function testResults(root, report) {
  const passed = report.tests.filter((t) => t.outcome === "passed").length;
  const list = el("ul", "edit-tests");
  for (const t of report.tests) {
    const item = el("li", t.outcome);
    item.dataset.test = t.name;
    item.append(el("code", "", t.name));
    if (t.message) item.append(el("span", "wb-message", t.message));
    list.append(item);
  }
  if (!report.tests.length) root.append(el("pre", "wb-output", report.output));
  else root.append(list);
  return passed;
}

/**
 * Say which of the page's figures and panels were computed for the book's query, while the
 * reader's edit of it is what ran last; `edited` false takes the notes away again.
 */
function markTheBooks(query, edited) {
  for (const node of document.querySelectorAll(`#main [data-query="${CSS.escape(query)}"]:not(button)`)) {
    node.querySelector(":scope > .stale-note")?.remove();
    delete node.dataset.stale;
    if (!edited) continue;
    node.dataset.stale = "true";
    node.prepend(el("p", "stale-note", "This result uses the book's original query."));
  }
}

function mountEdit(figure, then) {
  const file = figure.dataset.file;
  const pre = figure.querySelector(":scope > pre");
  if (!pre) return;
  const listing = pre.textContent.replace(/\n$/, "");
  const query = file.startsWith("queries/");
  const first = listing.split("\n").find((l) => l.trim()) || "";
  const key = `edit:${bookPath}:${file}:${first.trim()}`;
  figure.dataset.editable = query ? "query" : "code";

  const open = el("button", "edit-open", "Edit and run");
  open.type = "button";
  const bar = figure.querySelector(".source-bar");
  bar.querySelector(".source-label").after(open);

  let editor = null;
  function close() {
    // The editor sits in a box with the layer that colours it: both go.
    editor.closest(".code-edit").remove();
    figure.querySelector(".edit-bar").remove();
    figure.querySelector(".run-result").remove();
    editor = null;
    pre.hidden = false;
    if (query) markTheBooks(file.slice("queries/".length), false);
    open.textContent = "Edit and run";
    delete figure.dataset.editing;
  }

  function start() {
    pre.hidden = true;
    editor = el("textarea", "code-area");
    editor.spellcheck = false;
    editor.setAttribute("autocapitalize", "off");
    editor.setAttribute("autocomplete", "off");
    editor.setAttribute("aria-label", query ? "The query" : `Your edit of ${file}`);
    editor.value = store.get(key) ?? listing;
    editor.rows = Math.min(30, editor.value.split("\n").length + 1);
    const tools = el("div", "edit-bar");
    const run = el("button", "lab-run", query ? "Run the query" : "Run the listing");
    run.type = "button";
    const reset = el("button", "edit-reset", "Reset to the book's code");
    reset.type = "button";
    const recover = el("button", "edit-recover", "Recover saved draft");
    recover.type = "button";
    const hint = el("span", "lab-hint", query
      ? "Ctrl+Enter runs it under DuckDB in your browser. Your edit stays in this browser."
      : then.script
        ? (then.script === figure.dataset.file
          ? "Ctrl+Enter runs it as a script, and shows what it prints. Your edit stays in this browser."
          : `Ctrl+Enter runs ${then.script.split("/").pop()} with your edit in place, and shows what it prints. Your edit stays in this browser.`)
        : `Ctrl+Enter runs it in place of the engine's code, then ${then.tests ? "the engine's tests" : "the panel's report"}. Your edit stays in this browser.`);
    tools.append(run, reset, recover, hint);
    pre.after(editor, tools);
    const redraw = colour(editor, query ? "sql" : "python");
    const result = el("div", "lab run-result");
    const notice = el("p", "run-notice");
    notice.setAttribute("role", "status");
    const status = el("p", "lab-status");
    status.setAttribute("aria-live", "polite");
    let body = el("div", "lab-body");
    result.append(notice, status, body);
    const message = (text, error = false) => {
      notice.textContent = text;
      notice.classList.toggle("lab-error", error);
    };
    // The output belongs to the listing, so it goes where the listing goes: when the listing is
    // expanded to the whole window, its output is in the window too.
    figure.append(result);
    figure.dataset.editing = "true";
    open.textContent = "Close the editor";

    editor.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run.click(); }
    });
    const queryName = query ? file.slice("queries/".length) : null;
    const markDraft = (switched) => {
      if (!switched) return;
      body.replaceChildren();
      status.textContent = "";
      delete result.dataset.ready;
      delete result.dataset.agrees;
      delete result.dataset.passed;
      delete result.dataset.total;
      if (queryName) markTheBooks(queryName, false);
    };
    bindDraft(editor, {
      key, original: listing, reset, recover, redraw, onChange: markDraft, onMessage: message,
    });
    run.addEventListener("click", async () => {
      run.disabled = reset.disabled = recover.disabled = true;
      result.dataset.ready = "running";
      message("Running in your browser…");
      const text = editor.value;
      const edited = text !== listing;
      const next = el("div", "lab-body");
      let label;
      try {
        if (query) {
          const config = { experiment: "plan", query: queryName };
          const json = await runReport(edited ? { ...config, sql: text } : config, message);
          EXPERIMENTS.plan(next, JSON.parse(json), { store: revealed, key });
          label = edited
            ? "Your query result from the last successful run in DuckDB."
            : "The book's query result from its last successful run in DuckDB.";
          if (result.isConnected) markTheBooks(queryName, edited);
        } else {
          const answer = JSON.parse(await runEdit(file, listing, text, then, message));
          if (answer.error) throw new Error(answer.error);
          if (answer.output !== undefined && !answer.tests) {
            next.append(el("pre", "cell-output", answer.output));
            label = edited ? "Output from your last successful run." : "Output from running the book's listing.";
          } else if (answer.report) {
            EXPERIMENTS[then.report.experiment](next, answer.report, { store: revealed, key });
            if (edited) {
              label = "Counts from your last successful run.";
              delete result.dataset.agrees;
            } else {
              const same = JSON.stringify(answer.report) === JSON.stringify(then.build);
              result.dataset.agrees = String(same);
              label = same
                ? "The book's code, run in your browser. The counts match the worked result."
                : "The book's code, run in your browser. The counts differ from the worked result.";
            }
          } else {
            if (answer.exit > 1) throw new Error(lastLine({ message: answer.output }));
            const passed = testResults(next, answer);
            result.dataset.passed = String(passed);
            result.dataset.total = String(answer.tests.length);
            label = `${passed} of ${answer.tests.length} engine tests pass on ${edited ? "your edit" : "the book's code"}.`;
          }
        }
        body.replaceWith(next);
        body = next;
        status.textContent = label;
        message("");
        result.dataset.ready = "true";
        // The output can land below the window, an expanded listing's above all: bring it into view.
        result.scrollIntoView({ block: "nearest" });
      } catch (error) {
        const failure = query
          ? `DuckDB could not run your query: ${lastLine(error)}`
          : `${edited ? "Your edit" : "The book's listing"} could not run: ${lastLine(error)}`;
        message(failure, true);
        result.dataset.ready = "error";
      } finally {
        run.disabled = reset.disabled = recover.disabled = false;
      }
    });
  }

  open.addEventListener("click", () => (editor ? close() : start()));
  // Reopen an active edit. A recovery copy can be found by opening the editor.
  if (store.get(key) !== null && store.get(key) !== listing) start();
}

/** Lines a listing shows before it folds: the rest sit behind a button, so a long listing does
 * not push the prose around it off the screen. */
const FOLD_AT = 30;

function fold(figure) {
  const pre = figure.querySelector(":scope > pre");
  if (!pre) return;
  const lines = pre.textContent.replace(/\n$/, "").split("\n").length;
  if (lines <= FOLD_AT) return;
  figure.dataset.folded = "true";
  const toggle = el("button", "fold-toggle", `Show all ${lines} lines`);
  toggle.type = "button";
  toggle.addEventListener("click", () => {
    const folded = figure.dataset.folded === "true";
    figure.dataset.folded = String(!folded);
    toggle.textContent = folded ? "Show fewer lines" : `Show all ${lines} lines`;
  });
  pre.after(toggle);
}

/** Make every quoted query, and every engine listing a `run` block follows, editable, and fold
 * every long listing. */
export function mountEdits() {
  for (const figure of document.querySelectorAll("#main figure.quoted")) {
    // A script the page runs whole is read whole, as a notebook cell is: it never folds.
    const next = figure.nextElementSibling;
    const script = next && next.matches("script.run-then") && JSON.parse(next.textContent).script === figure.dataset.file;
    if (script) figure.dataset.script = "true";
    else fold(figure);
  }
  for (const figure of document.querySelectorAll("#main figure.quoted[data-file]")) {
    const next = figure.nextElementSibling;
    const then = next && next.matches("script.run-then") ? JSON.parse(next.textContent) : null;
    if (figure.dataset.file.startsWith("queries/") || then) mountEdit(figure, then);
  }
}
