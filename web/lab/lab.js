// Mount every panel on the page.
//
// A chapter marks a panel with a fenced block in the language `lab`; tools/render.py turns it into
// <div class="lab" data-experiment=… data-query=…> holding the JSON the build computed for it, with
// `query_lab.report` at a desk. The panel draws that JSON at once: nothing to download.
//
// Each panel also offers to run the same report in the reader's browser, under Pyodide
// (runner.js), and redraws from what it returns. Run as the book ships it, the page says whether
// the browser's answer is the build's; tests/browser/panels.mjs requires that it is. A panel with
// a query lets the reader edit it: the edit runs through the same report, is kept in the
// browser's storage, and is never compared with the build, because the build never ran it.
// JavaScript here draws JSON and compares it; it never computes a count of its own.

import { mountPlan } from "./plan.js";
import { runReport } from "./runner.js";

const EXPERIMENTS = { plan: mountPlan };

const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch {} },
  drop(key) { try { localStorage.removeItem(key); } catch {} },
};

/** The last line of a Python error: the exception and its message, without the traceback. */
function lastLine(error) {
  const lines = String(error.message || error).split("\n").map((l) => l.trim()).filter(Boolean);
  return lines[lines.length - 1] || "unknown error";
}

function mount(el) {
  const config = { experiment: el.dataset.experiment, query: el.dataset.query };
  if (!config.query) delete config.query;
  const draw = EXPERIMENTS[config.experiment];
  const built = el.querySelector("script.lab-data").textContent;
  const build = JSON.parse(built);
  const key = `lab:${config.experiment}:${config.query || ""}`;

  const body = document.createElement("div");
  body.className = "lab-body";
  const foot = document.createElement("div");
  foot.className = "lab-foot";
  const run = document.createElement("button");
  run.type = "button";
  run.className = "lab-run";
  run.textContent = "Run it in your browser";
  const status = document.createElement("p");
  status.className = "lab-status";
  status.setAttribute("aria-live", "polite");
  foot.append(run, status);
  // The fallback (the run as a table, for readers without JavaScript) stays in the page for
  // printing; lab.css hides it on screen once the panel is drawn.
  el.append(body);

  // The editor, for a panel whose report ran a query: the query as the build ran it, or the
  // reader's last edit of it.
  let editor = null;
  if (typeof build.source === "string") {
    const details = document.createElement("details");
    details.className = "lab-editor";
    details.innerHTML = `<summary>Edit the query</summary>
      <textarea class="code-area" spellcheck="false" autocapitalize="off" autocomplete="off" aria-label="The query"></textarea>
      <div class="lab-editor-bar"><button type="button" class="lab-reset">Reset to the book's query</button>
      <span class="lab-hint">Ctrl+Enter runs it. Your edit stays in this browser.</span></div>`;
    editor = details.querySelector("textarea");
    const saved = store.get(key);
    editor.value = saved ?? build.source;
    editor.rows = Math.min(14, editor.value.split("\n").length + 1);
    details.open = saved !== null && saved !== build.source;
    editor.addEventListener("input", () => {
      if (editor.value === build.source) store.drop(key);
      else store.set(key, editor.value);
      el.dataset.edited = String(editor.value !== build.source);
    });
    editor.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run.click(); }
    });
    details.querySelector(".lab-reset").addEventListener("click", () => {
      editor.value = build.source;
      if (store.get(key) !== null) store.drop(key);
      el.dataset.edited = "false";
      show(built, "build");
    });
    el.dataset.edited = String(editor.value !== build.source);
    el.append(details);
  }
  el.append(foot);

  function show(json, source) {
    const data = JSON.parse(json);
    body.replaceChildren();
    draw(body, data, { store, key });
    el.dataset.source = source;
    delete el.dataset.agrees;
    status.classList.remove("lab-error");
    status.textContent = source === "build"
      ? `Computed by ${data.engine} when the book was built.`
      : "";
  }
  show(built, "build");
  el.dataset.ready = "true";

  run.addEventListener("click", async () => {
    const edited = editor !== null && editor.value !== build.source;
    run.disabled = true;
    el.dataset.ready = "running";
    try {
      const json = await runReport(edited ? { ...config, sql: editor.value } : config,
        (text) => { status.textContent = text; });
      show(json, "browser");
      const engine = JSON.parse(json).engine;
      if (edited) {
        status.textContent = `Your query, run in your browser by ${engine} under Pyodide.`;
      } else {
        // Compared as parsed and re-serialised, so escaping inside the page's script element
        // cannot make two equal answers look different.
        const same = JSON.stringify(JSON.parse(json)) === JSON.stringify(build);
        el.dataset.agrees = String(same);
        status.textContent = same
          ? `Recomputed in your browser by ${engine} under Pyodide: the same answer as the build.`
          : "Recomputed in your browser: this differs from the build's answer. Please report it.";
        status.classList.toggle("lab-error", !same);
      }
      el.dataset.ready = "true";
    } catch (error) {
      status.textContent = edited
        ? `DuckDB could not run your query: ${lastLine(error)}`
        : `The panel could not run in your browser: ${lastLine(error)}`;
      status.classList.add("lab-error");
      el.dataset.ready = "error";
    } finally {
      run.disabled = false;
    }
  });
}

for (const el of document.querySelectorAll(".lab[data-experiment]")) {
  try {
    mount(el);
  } catch (error) {
    const message = document.createElement("p");
    message.className = "lab-error";
    message.textContent = `The panel could not be drawn: ${String(error.message || error)}`;
    el.replaceChildren(message);
    el.dataset.ready = "error";
  }
}
