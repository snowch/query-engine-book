// A chapter's problems, in the page: the reader edits the chapter's stubs and runs its graders.
//
// The graders are the repository's own (exercises/tests/test_<chapter>.py), run by pytest under
// Pyodide in the page's Python worker (runner.js) on the reader's text. The page draws what pytest
// reported, test by test, grouped by problem; it decides nothing itself. The reader's text is kept
// in the browser's storage under a key named for this book, since other books share the origin.

import { colour } from "./highlight.js";
import { runProblems } from "./runner.js";

const BOOK = location.pathname.replace(/[^/]*$/, "");

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch {} },
  drop(key) { try { localStorage.removeItem(key); } catch {} },
};

/** Which problem a grader belongs to: test_problem_1_1_… is problem 1.1. */
function problemOf(name) {
  const m = /^test_problem_(\d+)_(\d+)_/.exec(name);
  return m ? `${m[1]}.${m[2]}` : "other";
}

function results(root, report) {
  root.replaceChildren();
  const groups = new Map();
  for (const t of report.tests) {
    const key = problemOf(t.name);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(t);
  }
  for (const [problem, tests] of groups) {
    const passed = tests.filter((t) => t.outcome === "passed").length;
    const box = el("details", `wb-problem ${passed === tests.length ? "pass" : "fail"}`);
    box.dataset.problem = problem;
    box.open = passed !== tests.length;
    box.append(el("summary", "", `Problem ${problem}: ${passed} of ${tests.length} checks pass`));
    const list = el("ul");
    for (const t of tests) {
      const item = el("li", t.outcome);
      item.dataset.test = t.name;
      item.append(el("code", "", t.name.replace(/^test_problem_\d+_\d+_/, "")));
      if (t.message) item.append(el("span", "wb-message", t.message));
      list.append(item);
    }
    box.append(list);
    root.append(box);
  }
  if (!report.tests.length) root.append(el("pre", "wb-output", report.output));
}

export async function mountWorkbench(root) {
  const chapter = root.dataset.chapter;
  const key = `problems:${BOOK}:${chapter}`;
  const response = await fetch(new URL(`py/exercises/${chapter}.py`, import.meta.url));
  if (!response.ok) throw new Error(`could not fetch the problems: ${response.status}`);
  const stubs = await response.text();

  root.replaceChildren();
  const head = el("div", "lab-head");
  head.append(el("span", "lab-title", "Your answers"), el("code", "lab-note", `exercises/${chapter}.py`));
  const editor = el("textarea", "code-area");
  editor.spellcheck = false;
  editor.setAttribute("autocapitalize", "off");
  editor.setAttribute("aria-label", "Your answers to this chapter's problems");
  editor.value = store.get(key) ?? stubs;
  editor.rows = 24;
  const bar = el("div", "lab-foot");
  const run = el("button", "lab-run", "Run the graders");
  run.type = "button";
  const reset = el("button", "", "Reset to the stubs");
  reset.type = "button";
  const status = el("p", "lab-status", "Your answers stay in this browser. Ctrl+Enter runs the graders.");
  status.setAttribute("aria-live", "polite");
  bar.append(run, reset, status);
  const out = el("div", "wb-results");
  root.append(head, editor, bar, out);
  const redraw = colour(editor, "python");
  root.dataset.ready = "true";

  editor.addEventListener("input", () => {
    if (editor.value === stubs) store.drop(key);
    else store.set(key, editor.value);
  });
  editor.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run.click(); }
    // A tab in the editor indents, as it would in any code editor, rather than leaving the box.
    if (e.key === "Tab" && !e.shiftKey) {
      e.preventDefault();
      editor.setRangeText("    ", editor.selectionStart, editor.selectionEnd, "end");
      editor.dispatchEvent(new Event("input"));
    }
  });
  reset.addEventListener("click", () => {
    editor.value = stubs;
    redraw();
    store.drop(key);
    out.replaceChildren();
    status.textContent = "Reset to the stubs the book ships.";
  });
  run.addEventListener("click", async () => {
    run.disabled = true;
    root.dataset.ready = "running";
    status.classList.remove("lab-error");
    try {
      const report = JSON.parse(await runProblems(chapter, editor.value, (text) => { status.textContent = text; }));
      results(out, report);
      const passed = report.tests.filter((t) => t.outcome === "passed").length;
      status.textContent = `${passed} of ${report.tests.length} checks pass.`;
      root.dataset.ready = "true";
    } catch (error) {
      status.textContent = `The graders could not run: ${String(error.message || error).trim().split("\n").pop()}`;
      status.classList.add("lab-error");
      root.dataset.ready = "error";
    } finally {
      run.disabled = false;
    }
  });
}
