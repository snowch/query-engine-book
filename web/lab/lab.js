// Mount every panel on the page.
//
// A chapter marks a panel with a fenced block in the language `lab`; tools/render.py turns it into
// <div class="lab" data-experiment=… data-query=…> holding the JSON the build computed for it, with
// `query_lab.report` at a desk. The panel draws that JSON at once: nothing to download.
//
// Each panel also offers to run the same report in the reader's browser, under Pyodide
// (runner.js), and redraws from what it returns. The page says whether the browser's answer is
// the build's answer; tests/browser/panels.mjs requires that it is. JavaScript here draws JSON and
// compares it; it never computes a count of its own.

import { mountPlan } from "./plan.js";
import { runReport } from "./runner.js";

const EXPERIMENTS = { plan: mountPlan };

function mount(el) {
  const config = { ...el.dataset };
  delete config.ready;
  delete config.source;
  const draw = EXPERIMENTS[config.experiment];
  const built = el.querySelector("script.lab-data").textContent;
  const body = document.createElement("div");
  body.className = "lab-body";
  const foot = document.createElement("div");
  foot.className = "lab-foot";
  const run = document.createElement("button");
  run.type = "button";
  run.textContent = "Run it in your browser";
  const status = document.createElement("p");
  status.className = "lab-status";
  status.setAttribute("aria-live", "polite");
  foot.append(run, status);
  el.querySelector(".lab-fallback")?.remove();
  el.append(body, foot);

  const show = (json, source) => {
    const data = JSON.parse(json);
    body.replaceChildren();
    draw(body, data);
    el.dataset.source = source;
    status.textContent = source === "build"
      ? `Computed by ${data.engine} when the book was built.`
      : "";
  };
  show(built, "build");
  el.dataset.ready = "true";

  run.addEventListener("click", async () => {
    run.disabled = true;
    el.dataset.ready = "running";
    try {
      const json = await runReport(config, (text) => { status.textContent = text; });
      show(json, "browser");
      // Compared as parsed and re-serialised, so escaping inside the page's script element
      // cannot make two equal answers look different.
      const same = JSON.stringify(JSON.parse(json)) === JSON.stringify(JSON.parse(built));
      el.dataset.agrees = String(same);
      status.textContent = same
        ? `Recomputed in your browser by ${JSON.parse(json).engine} under Pyodide: the same answer as the build.`
        : `Recomputed in your browser: this differs from the build's answer. Please report it.`;
      status.classList.toggle("lab-error", !same);
      el.dataset.ready = "true";
    } catch (error) {
      status.textContent = `The panel could not run in your browser: ${String(error.message || error)}`;
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
