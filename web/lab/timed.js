// A timed block: a chapter's cases, timed in the reader's browser when the reader asks.
//
// The page carries the cases (query_lab.timing.describe), never a time: a time written when the
// book was built would be the build machine's, and would differ at every build. Pressing the
// button times each case in turn, in the page's Python worker, and draws how long it took here
// and now. The times differ from run to run and machine to machine, and are slower under
// WebAssembly than at a desk, so the block says so, and draws each case against the fastest:
// what a time is good for is comparing cases measured together.
//
// Every time drawn is a field of what Python returned; the drawing only scales and formats them.

import { runTiming } from "./runner.js";

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** A time as a reader reads one: a fraction of a millisecond, milliseconds, or seconds. */
export function formatTime(seconds) {
  const ms = seconds * 1000;
  if (ms < 1) return `${ms.toFixed(2)} ms`;
  if (ms < 1000) return `${ms.toFixed(ms < 10 ? 1 : 0)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function bar(share, kind) {
  const track = el("span", `timed-track ${kind}`);
  const fill = el("span", "timed-fill");
  fill.style.width = `${Math.max(0.5, Math.min(100, 100 * share))}%`;
  track.append(fill);
  return track;
}

/** Where a case's time went, operator by operator, as a share of the whole. */
function profileOf(profile) {
  const total = profile.reduce((sum, [, , s]) => sum + s, 0) || 1;
  const list = el("div", "timed-profile");
  list.append(el("div", "timed-profile-head", "Where the time went, each operator less its children"));
  for (const [operator, depth, seconds] of profile) {
    const row = el("div", "timed-op");
    row.dataset.operator = operator;
    const name = el("span", "timed-op-name", operator);
    name.style.paddingLeft = `${depth}rem`;
    row.append(name, bar(seconds / total, "share"), el("span", "timed-op-share", `${Math.round((100 * seconds) / total)}%`));
    list.append(row);
  }
  return list;
}

export function mountTimed(root) {
  const data = JSON.parse(root.querySelector("script.timed-data").textContent);
  root.querySelector(".lab-fallback")?.remove();
  root.classList.add("lab");

  const head = el("div", "lab-head");
  head.append(el("span", "lab-title", data.title));
  if (data.data) head.append(el("span", "lab-note", data.data));

  const list = el("ol", "timed-cases");
  const rows = data.cases.map((c) => {
    const item = el("li", "timed-case");
    item.dataset.case = c.label;
    const top = el("div", "timed-row");
    const value = el("span", "timed-value", "not timed yet");
    top.append(el("span", "timed-label", c.label), value);
    const track = bar(0, "time");
    const detail = el("code", "timed-detail", c.detail);
    const more = el("div", "timed-more");
    item.append(top, track, detail, more);
    list.append(item);
    return { item, value, track, more };
  });

  const foot = el("div", "lab-foot");
  const button = el("button", "lab-run", "Time it in your browser");
  button.type = "button";
  const status = el("p", "lab-status");
  status.setAttribute("aria-live", "polite");
  foot.append(button, status);

  const caveat = el("p", "timed-caveat",
    "A time is measured when you press the button, on your machine, and the page keeps none. "
    + "It differs from run to run, and Python under WebAssembly in a browser runs slower than at a desk. "
    + "Compare the cases with each other, not with a time measured anywhere else.");

  root.append(head, list, foot, caveat);
  root.dataset.ready = "true";

  button.addEventListener("click", async () => {
    button.disabled = true;
    root.dataset.ready = "running";
    status.classList.remove("lab-error");
    const times = [];
    let where = "";
    try {
      for (const [index, c] of data.cases.entries()) {
        const row = rows[index];
        row.value.textContent = "timing…";
        row.item.classList.add("timing");
        const label = `Timing ${index + 1} of ${data.cases.length}: ${c.label}…`;
        const result = JSON.parse(await runTiming(data.of, index, label, (text) => { status.textContent = text; }));
        row.item.classList.remove("timing");
        times[index] = result.seconds;
        where = result.where;
        row.item.dataset.seconds = String(result.seconds);
        row.value.textContent = `${formatTime(result.seconds)} · ${result.runs.toLocaleString("en-GB")} ${result.runs === 1 ? "run" : "runs"}`;
        row.more.replaceChildren(...(result.profile ? [profileOf(result.profile)] : []));
        // Every bar on one scale, the slowest case so far the full width.
        const slowest = Math.max(...times.filter((t) => t !== undefined));
        rows.forEach((r, i) => {
          if (times[i] !== undefined) r.track.querySelector(".timed-fill").style.width = `${Math.max(0.5, (100 * times[i]) / slowest)}%`;
        });
      }
      const fastest = Math.min(...times);
      rows.forEach((r, i) => {
        const ratio = times[i] / fastest;
        const against = ratio < 1.05 ? "the fastest" : `${ratio < 10 ? ratio.toFixed(1) : Math.round(ratio)}× the fastest`;
        r.value.textContent += ` · ${against}`;
      });
      status.textContent = `Timed in ${where}. Press again to see how much the times move.`;
      button.textContent = "Time it again";
      root.dataset.ready = "true";
    } catch (error) {
      rows.forEach((r) => r.item.classList.remove("timing"));
      const lines = String(error.message || error).split("\n").filter((l) => l.trim());
      status.textContent = `The cases could not be timed: ${lines[lines.length - 1] || "unknown error"}`;
      status.classList.add("lab-error");
      root.dataset.ready = "error";
    } finally {
      button.disabled = false;
    }
  });
}
