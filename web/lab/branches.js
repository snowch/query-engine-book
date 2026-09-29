// The branches panel: which rows of the orders pass a test, found with a branch and without one,
// through the branch predictor model, from query_lab.report.branches.
//
// It asks first and answers second, as the gather panel does. Each case shows its test, how it
// is run and the values it tests, and a box for the reader's prediction of the mispredictions.
// The measurement stays hidden until the reader reveals it. Then each case has three bars on one
// scale: your prediction, the values tested, and the mispredictions; under them the predictor's
// counters; and under the cases, the sweep: the mispredictions of the random test at every
// threshold, with a branch and without.
//
// Every number drawn is a field of the report's JSON or a number the reader typed. The sweep's
// points are placed from the report's counts; nothing here counts.

const fmt = (n) => Number(n).toLocaleString("en-GB");
const SVG = "http://www.w3.org/2000/svg";

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

function svg(tag, attrs) {
  const e = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  return e;
}

function bar(label, value, max, kind, missing = "none") {
  const row = el("div", `plan-bar ${kind}`);
  row.append(el("span", "plan-bar-label", label));
  const track = el("span", "plan-bar-track");
  const fill = el("span", "plan-bar-fill");
  fill.style.width = `${max && value !== null ? Math.min(100, (100 * value) / max) : 0}%`;
  track.append(fill);
  row.append(track, el("span", "plan-bar-value", value === null ? missing : fmt(value)));
  return row;
}

function predictionBox(value, onInput) {
  const row = el("label", "plan-bar predicted plan-predict");
  row.append(el("span", "plan-bar-label", "You predict"));
  const input = el("input");
  input.type = "number";
  input.min = "0";
  input.step = "1";
  input.inputMode = "numeric";
  input.placeholder = "mispredictions";
  if (value !== undefined) input.value = String(value);
  input.addEventListener("input", () => onInput(input.value === "" ? undefined : Math.max(0, Math.round(Number(input.value)))));
  row.append(input);
  return row;
}

function card(c, view, index) {
  const slot = `${index}:${c.label}`;
  const box = el("div", "plan-op branch-case");
  box.dataset.case = c.label;
  const name = el("div", "plan-op-name");
  name.append(el("code", "", c.test), `, ${c.kernel}`);
  box.append(name);
  const bars = el("div", "plan-bars");
  const predicted = view.predictions[slot];
  if (view.asking) {
    bars.append(
      predictionBox(predicted, (v) => view.predict(slot, v)),
      bar("Values tested", c.rows, view.max, "estimated"),
      bar("Mispredicted", null, view.max, "measured hidden", "hidden"),
    );
  } else {
    bars.append(
      bar("You predicted", predicted ?? null, view.max, "predicted", "no guess"),
      bar("Values tested", c.rows, view.max, "estimated"),
      bar("Mispredicted", c.mispredictions, view.max, "measured"),
    );
  }
  box.append(bars);
  if (!view.asking) {
    const flow = el("div", "plan-op-flow");
    for (const [label, field] of [["branches", "branches"], ["mispredictions", "mispredictions"], ["kept", "kept"]]) {
      const b = el("b", "", fmt(c[field]));
      b.dataset.field = field;
      flow.append(el("span", "", label), " ", b, " ");
    }
    box.append(flow);
  }
  return box;
}

/** The sweep: across, the share of the rows the test keeps; up, the mispredictions. */
function sweep(data) {
  const w = 320, h = 150, left = 8, right = 8, top = 8, bottom = 22;
  const most = Math.max(1, ...data.sweep.map((p) => Math.max(p.with, p.without)));
  const x = (p) => left + ((w - left - right) * p.kept) / data.rows;
  const y = (v) => top + (h - top - bottom) * (1 - v / most);
  const chart = svg("svg", { viewBox: `0 0 ${w} ${h}`, class: "branch-sweep", role: "img",
    "aria-label": `Mispredictions against the share of the rows kept, for ${data.sweep.length} thresholds, with a branch and without` });
  chart.append(svg("line", { x1: left, y1: h - bottom, x2: w - right, y2: h - bottom, class: "branch-axis" }));
  for (const [kind, field] of [["with", "with"], ["without", "without"]]) {
    const points = data.sweep.map((p) => `${x(p)},${y(p[field])}`).join(" ");
    chart.append(svg("polyline", { points, class: `branch-line ${kind}` }));
    for (const p of data.sweep) {
      const dot = svg("circle", { cx: x(p), cy: y(p[field]), r: 2.4, class: `branch-dot ${kind}` });
      dot.dataset.kept = p.kept;
      dot.dataset.mispredictions = p[field];
      chart.append(dot);
    }
  }
  const none = svg("text", { x: left, y: h - 6, class: "branch-label" });
  none.textContent = "keeps none";
  const all = svg("text", { x: w - right, y: h - 6, class: "branch-label end" });
  all.textContent = "keeps every row";
  chart.append(none, all);
  const figure = el("figure", "branch-figure");
  figure.append(chart);
  const caption = el("figcaption");
  caption.append(`The test on `, el("code", "", data.column), ` at ${fmt(data.sweep.length)} thresholds. Across: the share of the rows it keeps. Up: mispredictions, `);
  const top_ = el("b", "", fmt(most));
  top_.dataset.field = "most";
  caption.append("at most ", top_, ". ");
  caption.append(el("span", "branch-key with", "With a branch"), " ", el("span", "branch-key without", "without"), ".");
  figure.append(caption);
  return figure;
}

/**
 * Draw `data` into `root`. `ctx.store` keeps the reader's predictions and whether they revealed
 * the measurement, under `ctx.key`, so both survive a reload and a rerun in the browser.
 */
export function mountBranches(root, data, ctx) {
  const saved = (() => {
    try { return JSON.parse(ctx.store.get(`${ctx.key}:predict`) || "null"); } catch { return null; }
  })() || { predictions: {}, revealed: false };
  const save = () => ctx.store.set(`${ctx.key}:predict`, JSON.stringify(saved));
  const redraw = () => { root.replaceChildren(); mountBranches(root, data, ctx); };

  const asking = !saved.revealed;
  const guesses = Object.values(saved.predictions);
  // Before the reveal, scaled to the values tested alone, so no bar's length hints at the answer.
  const max = Math.max(1, data.rows, ...(asking ? [] : [...data.cases.map((c) => c.mispredictions), ...guesses]));
  root.dataset.asking = String(asking);

  const head = el("div", "lab-head");
  head.append(el("span", "lab-title", asking
    ? "Testing every row: predict the mispredictions of each way"
    : "Testing every row, as it ran"));
  if (!asking) {
    const again = el("button", "plan-again", "Predict again");
    again.type = "button";
    again.addEventListener("click", () => {
      saved.predictions = {};
      saved.revealed = false;
      save();
      redraw();
    });
    head.append(again);
  }
  root.append(head);

  const facts = el("p", "branch-facts");
  const rows = el("b", "", fmt(data.rows));
  rows.dataset.field = "rows";
  facts.append(rows, " rows of ", el("code", "", data.fixture), ", in date order. With a branch, each value costs two: the test's, and the loop's. Without one, only the loop's.");
  root.append(facts);

  const view = {
    asking, max,
    predictions: saved.predictions,
    predict(slot, value) {
      if (value === undefined) delete saved.predictions[slot];
      else saved.predictions[slot] = value;
      save();
    },
  };
  const cases = el("div", "gather-runs");
  data.cases.forEach((c, i) => cases.append(card(c, view, i)));
  root.append(cases);

  if (asking) {
    const ask = el("div", "plan-ask");
    const reveal = el("button", "plan-reveal", "Reveal the measurement");
    reveal.type = "button";
    reveal.addEventListener("click", () => {
      saved.revealed = true;
      save();
      redraw();
    });
    ask.append(reveal, el("span", "lab-hint",
      "Type your prediction of each case's mispredictions first, or reveal without guessing."));
    root.append(ask);
  } else {
    root.append(sweep(data));
  }
}
