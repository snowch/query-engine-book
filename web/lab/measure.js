// The measure panel: the book's general predict-then-reveal panel, from query_lab.report.measure.
//
// A chapter's report names what the reader predicts (`predict.label`), and gives cases: each with
// a label, a detail (usually a query or a setting, shown as code), a reference bar the reader
// predicts against, and the measurement, hidden until the reader reveals it. Revealed, each case
// has three bars on one scale (your prediction, the reference, the measurement) and under them
// its counters; and a report that has a `chart` draws it under the cases: lines of points, each
// point a pair of numbers from the report, on a linear or a logarithmic scale.
//
// Every number drawn is a field of the report's JSON or a number the reader typed. Nothing here
// counts.

const fmt = (n) => Number(n).toLocaleString("en-GB", { maximumFractionDigits: 2 });
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

function predictionBox(placeholder, value, onInput) {
  const row = el("label", "plan-bar predicted plan-predict");
  row.append(el("span", "plan-bar-label", "You predict"));
  const input = el("input");
  input.type = "number";
  input.min = "0";
  input.step = "any";
  input.inputMode = "decimal";
  input.placeholder = placeholder;
  if (value !== undefined) input.value = String(value);
  input.addEventListener("input", () => onInput(input.value === "" ? undefined : Math.max(0, Number(input.value))));
  row.append(input);
  return row;
}

function card(c, data, view, index) {
  const slot = `${index}:${c.label}`;
  const box = el("div", "plan-op measure-case");
  box.dataset.case = c.label;
  const name = el("div", "plan-op-name", c.label);
  box.append(name);
  if (c.detail) box.append(el("code", "measure-detail", c.detail));
  const bars = el("div", "plan-bars");
  const predicted = view.predictions[slot];
  if (view.asking) {
    bars.append(
      predictionBox(data.predict.placeholder, predicted, (v) => view.predict(slot, v)),
      bar(c.reference.label, c.reference.value, view.max, "estimated"),
      bar(data.predict.label, null, view.max, "measured hidden", "hidden"),
    );
  } else {
    bars.append(
      bar("You predicted", predicted ?? null, view.max, "predicted", "no guess"),
      bar(c.reference.label, c.reference.value, view.max, "estimated"),
      bar(data.predict.label, c.measured, view.max, "measured"),
    );
  }
  box.append(bars);
  if (!view.asking && c.counters.length) {
    const flow = el("div", "plan-op-flow");
    c.counters.forEach(([label, value], i) => {
      const b = el("b", "", fmt(value));
      b.dataset.counter = String(i);
      flow.append(el("span", "", label), " ", b, " ");
    });
    box.append(flow);
  }
  return box;
}

/** The report's chart: each series a line through its points, on the report's scales. */
function chart(spec) {
  const w = 340, h = 170, left = 10, right = 10, top = 10, bottom = 26;
  const xs = spec.series.flatMap((s) => s.points.map((p) => p[0]));
  const ys = spec.series.flatMap((s) => s.points.map((p) => p[1]));
  const log = spec.x_scale === "log";
  const fx = (v) => (log ? Math.log(Math.max(v, 1e-9)) : v);
  const lo = Math.min(...xs.map(fx)), hi = Math.max(...xs.map(fx));
  const most = Math.max(1e-9, ...ys);
  const x = (v) => left + ((w - left - right) * (fx(v) - lo)) / Math.max(1e-9, hi - lo);
  const y = (v) => top + (h - top - bottom) * (1 - v / most);
  const g = svg("svg", { viewBox: `0 0 ${w} ${h}`, class: "measure-chart", role: "img",
    "aria-label": `${spec.y_label} against ${spec.x_label}` });
  g.append(svg("line", { x1: left, y1: h - bottom, x2: w - right, y2: h - bottom, class: "measure-axis" }));
  spec.series.forEach((s, i) => {
    g.append(svg("polyline", { points: s.points.map((p) => `${x(p[0])},${y(p[1])}`).join(" "), class: `measure-line s${i}` }));
    for (const p of s.points) {
      const dot = svg("circle", { cx: x(p[0]), cy: y(p[1]), r: 2.4, class: `measure-dot s${i}` });
      dot.dataset.x = p[0];
      dot.dataset.y = p[1];
      g.append(dot);
    }
  });
  const first = svg("text", { x: left, y: h - 8, class: "measure-label" });
  first.textContent = fmt(Math.min(...xs));
  const last = svg("text", { x: w - right, y: h - 8, class: "measure-label end" });
  last.textContent = fmt(Math.max(...xs));
  g.append(first, last);
  const figure = el("figure", "measure-figure");
  figure.append(g);
  const caption = el("figcaption");
  caption.append(`Across: ${spec.x_label}${log ? ", on a logarithmic scale" : ""}. Up: ${spec.y_label}, at most `);
  const top_ = el("b", "", fmt(most));
  top_.dataset.field = "most";
  caption.append(top_, ". ");
  spec.series.forEach((s, i) => caption.append(el("span", `measure-key s${i}`, s.label), i + 1 < spec.series.length ? ", " : "."));
  figure.append(caption);
  return figure;
}

/**
 * Draw `data` into `root`. `ctx.store` keeps the reader's predictions and whether they revealed
 * the measurement, under `ctx.key`, so both survive a reload and a rerun in the browser.
 */
export function mountMeasure(root, data, ctx) {
  const saved = (() => {
    try { return JSON.parse(ctx.store.get(`${ctx.key}:predict`) || "null"); } catch { return null; }
  })() || { predictions: {}, revealed: false };
  const save = () => ctx.store.set(`${ctx.key}:predict`, JSON.stringify(saved));
  const redraw = () => { root.replaceChildren(); mountMeasure(root, data, ctx); };

  const asking = !saved.revealed;
  const guesses = Object.values(saved.predictions);
  // Before the reveal, scaled to the references alone, so no bar's length hints at the answer.
  const references = data.cases.map((c) => c.reference.value);
  const max = Math.max(1e-9, ...references, ...(asking ? [] : [...data.cases.map((c) => c.measured), ...guesses]));
  root.dataset.asking = String(asking);

  const head = el("div", "lab-head");
  head.append(el("span", "lab-title", asking ? `${data.title}: predict ${data.predict.ask}` : `${data.title}, as it ran`));
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
  if (data.facts) root.append(el("p", "measure-facts", data.facts));

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
  data.cases.forEach((c, i) => cases.append(card(c, data, view, i)));
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
    ask.append(reveal, el("span", "lab-hint", `Type your prediction for each case first, or reveal without guessing.`));
    root.append(ask);
  } else if (data.chart) {
    root.append(chart(data.chart));
  }
}
