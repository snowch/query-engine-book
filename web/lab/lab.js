// Mount every panel on the page.
//
// A chapter marks a panel with a fenced block in the language `lab`; tools/render.py turns it into
// <div class="lab" data-experiment=… data-query=…> holding the JSON the build computed for it, with
// `query_lab.report` when the book was built. The panel draws that JSON at once: nothing to download.
//
// Each panel also offers to run the same report in the reader's browser, under Pyodide
// (runner.js), and redraws from what it returns. Run as the book ships it, the page says whether
// the browser's answer is the build's; tests/browser/panels.mjs requires that it is. A panel with
// a query lets the reader edit it: the edit runs through the same report, is kept in the
// browser's storage, and is never compared with the build, because the build never ran it.
// JavaScript here draws JSON and compares it; it never computes a count of its own.

import { mountEdits } from "./edit.js";
import { bindDraft, bookPath, store } from "./drafts.js";
import { colour } from "./highlight.js";
import { EXPERIMENTS } from "./panels.js";
import { runReport } from "./runner.js";
import { mountTimed } from "./timed.js";
import { mountWorkbench } from "./workbench.js";

/** The last line of a Python error: the exception and its message, without the traceback. */
function lastLine(error) {
  const lines = String(error.message || error).split("\n").map((l) => l.trim()).filter(Boolean);
  return lines[lines.length - 1] || "unknown error";
}

function mount(el) {
  // The block's settings, as the renderer wrote them: nothing else is on the element yet.
  const config = { ...el.dataset };
  const draw = EXPERIMENTS[config.experiment];
  const built = el.querySelector("script.lab-data").textContent;
  const build = JSON.parse(built);
  // Named for this book: other books share the origin, and its storage.
  const settings = Object.keys(config).filter((k) => k !== "experiment").sort().map((k) => config[k]);
  const key = `lab:${bookPath}:${config.experiment}:${settings.join(":")}`;

  let body = document.createElement("div");
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
  const notice = document.createElement("p");
  notice.className = "run-notice";
  notice.setAttribute("role", "status");
  const message = (text, error = false) => {
    notice.textContent = text;
    notice.classList.toggle("lab-error", error);
  };
  foot.append(run, status, notice);
  el.querySelector(".lab-fallback")?.remove();
  el.append(body);

  // The editor, for a panel whose report ran a query: the query as the build ran it, or the
  // reader's last edit of it.
  let editor = null;
  let reset = null;
  let recover = null;
  if (typeof build.source === "string") {
    const details = document.createElement("details");
    details.className = "lab-editor";
    details.innerHTML = `<summary>Edit the query</summary>
      <textarea class="code-area" spellcheck="false" autocapitalize="off" autocomplete="off" aria-label="The query"></textarea>
      <div class="lab-editor-bar"><button type="button" class="lab-reset">Reset to the book's query</button>
      <button type="button" class="lab-recover">Recover saved draft</button>
      <span class="lab-hint">Ctrl+Enter runs it. Your edit stays in this browser.</span></div>`;
    editor = details.querySelector("textarea");
    reset = details.querySelector(".lab-reset");
    recover = details.querySelector(".lab-recover");
    const saved = store.get(key);
    editor.value = saved ?? build.source;
    editor.rows = Math.min(14, editor.value.split("\n").length + 1);
    details.open = saved !== null && saved !== build.source;
    editor.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run.click(); }
    });
    el.append(details);
    const redraw = colour(editor, "sql");
    const markDraft = (switched) => {
      const edited = editor.value !== build.source;
      el.dataset.edited = String(edited);
      run.textContent = edited ? "Run your query in your browser" : "Run the book's query in your browser";
      if (switched) {
        show(build, "build");
        el.dataset.ready = "true";
      }
    };
    bindDraft(editor, { key, original: build.source, reset, recover, redraw, onChange: markDraft, onMessage: message });
    markDraft(false);
  }
  el.append(foot);

  function show(data, source) {
    const next = document.createElement("div");
    next.className = "lab-body";
    draw(next, data, { store, key });
    body.replaceWith(next);
    body = next;
    el.dataset.source = source;
    delete el.dataset.agrees;
    status.textContent = source === "build"
      ? `Computed by ${data.engine} when the book was built.`
      : "";
  }
  show(build, "build");
  el.dataset.ready = "true";

  run.addEventListener("click", async () => {
    const sql = editor?.value;
    const edited = sql !== undefined && sql !== build.source;
    run.disabled = true;
    if (reset) reset.disabled = recover.disabled = true;
    el.dataset.ready = "running";
    message("Running in your browser…");
    try {
      const json = await runReport(edited ? { ...config, sql } : config, message);
      const data = JSON.parse(json);
      show(data, "browser");
      if (edited) {
        status.textContent = `Your query, run in your browser by ${data.engine} under Pyodide.`;
      } else {
        // Compared as parsed and re-serialised, so escaping inside the page's script element
        // cannot make two equal answers look different.
        const same = JSON.stringify(data) === JSON.stringify(build);
        el.dataset.agrees = String(same);
        status.textContent = same
          ? `Recomputed in your browser by ${data.engine} under Pyodide. The counts match the worked result.`
          : "Recomputed in your browser. The counts differ from the worked result. Please report the difference.";
      }
      message("");
      el.dataset.ready = "true";
    } catch (error) {
      const failure = edited
        ? `DuckDB could not run your query: ${lastLine(error)}`
        : `The panel could not run in your browser: ${lastLine(error)}`;
      message(`${failure}. The previous result is shown above.`, true);
      el.dataset.ready = "error";
    } finally {
      run.disabled = false;
      if (reset) reset.disabled = recover.disabled = false;
    }
  });
}

try {
  mountEdits();
} catch (error) {
  console.error("the listings could not be made editable", error);
}

for (const el of document.querySelectorAll(".workbench[data-chapter]")) {
  mountWorkbench(el).catch((error) => {
    const message = document.createElement("p");
    message.className = "lab-error";
    message.textContent = `The workbench could not start: ${String(error.message || error)}`;
    el.replaceChildren(message);
    el.dataset.ready = "error";
  });
}

for (const el of document.querySelectorAll(".timed[data-of]")) {
  try {
    mountTimed(el);
  } catch (error) {
    const message = document.createElement("p");
    message.className = "lab-error";
    message.textContent = `The timings could not be drawn: ${String(error.message || error)}`;
    el.replaceChildren(message);
    el.dataset.ready = "error";
  }
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
