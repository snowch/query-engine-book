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

import { EXPERIMENTS } from "./panels.js";
import { runEdit, runReport } from "./runner.js";

const BOOK = location.pathname.replace(/[^/]*$/, "");

const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch {} },
  drop(key) { try { localStorage.removeItem(key); } catch {} },
};

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

/** A value of the plan's result as the page shows it: a long fraction cut to a few places. */
function cell(value) {
  if (value === null) return "NULL";
  if (typeof value === "number" && !Number.isInteger(value)) return value.toLocaleString("en-GB", { maximumFractionDigits: 3 });
  return String(value);
}

function table(head, rows, className) {
  const t = el("table", className);
  const tr = el("tr");
  for (const h of head) tr.append(el("th", "", h));
  t.append(el("thead"));
  t.tHead.append(tr);
  const body = el("tbody");
  for (const row of rows) {
    const r = el("tr");
    for (const v of row) {
      const td = el("td");
      if (v instanceof Node) td.append(v);
      else td.textContent = v;
      r.append(td);
    }
    body.append(r);
  }
  t.append(body);
  return t;
}

/** What the plan returned and counted on the reader's edit: its first rows, and each operator's
 * counters, top down. Python computed every number; this only draws them. */
function shownResult(root, shown) {
  const box = el("div", "edit-shown");
  if (shown.error) {
    box.append(el("p", "lab-error", `The plan could not run: ${shown.error}`));
    root.append(box);
    return;
  }
  const rows = shown.total.toLocaleString("en-GB");
  box.append(el("p", "edit-shown-title", shown.rows.length < shown.total
    ? `The plan returned ${rows} rows. The first ${shown.rows.length}:`
    : `The plan returned ${rows} rows:`));
  const wrap = el("div", "table-wrap");
  wrap.append(table(shown.columns, shown.rows.map((r) => r.map(cell)), "edit-rows"));
  box.append(wrap);
  box.append(el("p", "edit-shown-title", "What each operator counted, from the top of the plan down:"));
  const counted = el("div", "table-wrap");
  counted.append(table(
    ["Operator", "Rows in", "Rows out", "Batches out", "Bytes read"],
    shown.operators.map((op) => {
      const name = el("span", "edit-op");
      name.style.paddingLeft = `${op.depth}em`;
      name.append(el("strong", "", op.operator), el("code", "", op.detail));
      return [name, op.rows_in.toLocaleString("en-GB"), op.rows_out.toLocaleString("en-GB"),
        op.batches_out.toLocaleString("en-GB"), op.bytes_read.toLocaleString("en-GB")];
    }),
    "edit-counters",
  ));
  box.append(counted);
  box.dataset.shown = JSON.stringify(shown);
  root.append(box);
}

/**
 * Say which of the page's figures and panels were computed for the book's query, while the
 * reader's edit of it is what ran last; `edited` false takes the notes away again.
 */
function markTheBooks(query, edited) {
  for (const node of document.querySelectorAll(`#main [data-query="${CSS.escape(query)}"]`)) {
    node.querySelector(":scope > .stale-note")?.remove();
    delete node.dataset.stale;
    if (!edited) continue;
    node.dataset.stale = "true";
    node.prepend(el("p", "stale-note", "Computed for the book's query, not your edit of it. Reset the query, and this matches again."));
  }
}

function mountEdit(figure, then) {
  const file = figure.dataset.file;
  const pre = figure.querySelector(":scope > pre");
  if (!pre) return;
  const listing = pre.textContent.replace(/\n$/, "");
  const query = file.startsWith("queries/");
  const first = listing.split("\n").find((l) => l.trim()) || "";
  const key = `edit:${BOOK}:${file}:${first.trim()}`;
  figure.dataset.editable = query ? "query" : "code";

  const open = el("button", "edit-open", "Edit and run");
  open.type = "button";
  const bar = figure.querySelector(".source-bar");
  bar.querySelector(".source-label").after(open);

  let editor = null;
  let result = null;

  function close() {
    editor.remove();
    figure.querySelector(".edit-bar").remove();
    result.remove();
    editor = result = null;
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
    const run = el("button", "lab-run", query ? "Run the query" : "Run your edit");
    run.type = "button";
    const reset = el("button", "edit-reset", "Reset to the book's code");
    reset.type = "button";
    const hint = el("span", "lab-hint", query
      ? "Ctrl+Enter runs it under DuckDB in your browser. Your edit stays in this browser."
      : `Ctrl+Enter runs it in place of the engine's code, then ${then.tests ? "the engine's tests" : "the panel's report"}. Your edit stays in this browser.`);
    tools.append(run, reset, hint);
    pre.after(editor, tools);
    result = el("div", "lab run-result");
    const status = el("p", "lab-status");
    status.setAttribute("aria-live", "polite");
    const body = el("div", "lab-body");
    result.append(status, body);
    figure.after(result);
    figure.dataset.editing = "true";
    open.textContent = "Close the editor";

    editor.addEventListener("input", () => {
      if (editor.value === listing) store.drop(key);
      else store.set(key, editor.value);
    });
    editor.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run.click(); }
      if (e.key === "Tab" && !e.shiftKey) {
        e.preventDefault();
        editor.setRangeText(query ? "  " : "    ", editor.selectionStart, editor.selectionEnd, "end");
        editor.dispatchEvent(new Event("input"));
      }
    });
    reset.addEventListener("click", () => {
      editor.value = listing;
      store.drop(key);
      body.replaceChildren();
      status.classList.remove("lab-error");
      status.textContent = "Reset to the code the book quotes.";
      if (query) markTheBooks(file.slice("queries/".length), false);
    });
    run.addEventListener("click", async () => {
      run.disabled = true;
      result.dataset.ready = "running";
      status.classList.remove("lab-error");
      body.replaceChildren();
      const text = editor.value;
      const edited = text !== listing;
      try {
        if (query) {
          const name = file.slice("queries/".length);
          const json = await runReport({ experiment: "plan", query: name, sql: text }, (t) => { status.textContent = t; });
          EXPERIMENTS.plan(body, JSON.parse(json), { store: revealed, key });
          status.textContent = edited
            ? "Your query, run in your browser by DuckDB under Pyodide. The figures computed for the book's query say so."
            : "The book's query, run in your browser by DuckDB under Pyodide.";
          markTheBooks(name, edited);
        } else {
          const answer = JSON.parse(await runEdit(file, listing, text, then, (t) => { status.textContent = t; }));
          if (answer.error) throw new Error(answer.error);
          if (answer.report) {
            EXPERIMENTS[then.report.experiment](body, answer.report, { store: revealed, key });
            const same = JSON.stringify(answer.report) === JSON.stringify(then.build);
            result.dataset.agrees = String(same);
            status.textContent = same
              ? (edited ? "Your edit gives the same answer as the book's code." : "The book's code, run in your browser: the same answer as the build.")
              : "Your edit changed the answer: this is what your code counted, and the panel above is the book's.";
          } else {
            const passed = testResults(body, answer);
            if (answer.shown) shownResult(body, answer.shown);
            result.dataset.passed = String(passed);
            result.dataset.total = String(answer.tests.length);
            status.textContent = `${passed} of ${answer.tests.length} of the engine's tests pass on ${edited ? "your edit" : "the book's code"}.`;
          }
        }
        result.dataset.ready = "true";
      } catch (error) {
        status.textContent = query
          ? `DuckDB could not run your query: ${lastLine(error)}`
          : `Your edit could not run: ${lastLine(error)}`;
        status.classList.add("lab-error");
        result.dataset.ready = "error";
      } finally {
        run.disabled = false;
      }
    });
  }

  open.addEventListener("click", () => (editor ? close() : start()));
  // An edit kept from an earlier visit opens its editor, so the reader sees their own code.
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
  for (const figure of document.querySelectorAll("#main figure.quoted")) fold(figure);
  for (const figure of document.querySelectorAll("#main figure.quoted[data-file]")) {
    const next = figure.nextElementSibling;
    const then = next && next.matches("script.run-then") ? JSON.parse(next.textContent) : null;
    if (figure.dataset.file.startsWith("queries/") || then) mountEdit(figure, then);
  }
}
