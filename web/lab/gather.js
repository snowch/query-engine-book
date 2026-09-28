// The gather panel: one column of the orders read into date order through the cache model, once
// from the file stored in date order and once from the shuffled file, from
// query_lab.report.gather.
//
// It asks first and answers second, as the plan panel does. Each gather shows the pattern of its
// reads (which line of the column every so many of them fell in) and the column's size in lines, and
// a box for the reader's prediction of the lines the cache had to fetch. The measurement stays
// hidden until the reader reveals it. Then each gather has three bars on one scale: your
// prediction, the column's lines, and the lines fetched; and under them the cache's counters.
//
// Every number drawn is a field of the report's JSON or a number the reader typed. The pattern's
// dots are placed from the report's line numbers; nothing here counts.

const fmt = (n) => Number(n).toLocaleString("en-GB");
const SVG = "http://www.w3.org/2000/svg";

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
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
  input.placeholder = "lines fetched";
  if (value !== undefined) input.value = String(value);
  input.addEventListener("input", () => onInput(input.value === "" ? undefined : Math.max(0, Math.round(Number(input.value)))));
  row.append(input);
  return row;
}

/** Each sampled read as a dot: across, when it came; up, the line of the column it fell in. */
function pattern(lines, columnLines) {
  const w = 320, h = 120, pad = 4;
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("class", "gather-pattern");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `The column's line for ${lines.length} reads, evenly spaced through the gather`);
  const span = Math.max(1, lines.length - 1);
  lines.forEach((line, i) => {
    const dot = document.createElementNS(SVG, "circle");
    dot.setAttribute("cx", String(pad + ((w - 2 * pad) * i) / span));
    dot.setAttribute("cy", String(h - pad - ((h - 2 * pad) * line) / Math.max(1, columnLines - 1)));
    dot.setAttribute("r", "1.8");
    svg.append(dot);
  });
  return svg;
}

function run(g, data, view, index) {
  const slot = `${index}:${g.fixture}`;
  const card = el("div", "plan-op gather-run");
  card.dataset.fixture = g.fixture;
  const name = el("div", "plan-op-name");
  name.append("From ", el("code", "", g.fixture));
  card.append(name);
  const figure = el("figure", "gather-figure");
  figure.append(pattern(g.pattern, data.column_lines));
  figure.append(el("figcaption", "", `Across: one read in every ${fmt(g.pattern_every)}, in date order. Up: the line of the column it falls in.`));
  card.append(figure);
  const bars = el("div", "plan-bars");
  const predicted = view.predictions[slot];
  if (view.asking) {
    bars.append(
      predictionBox(predicted, (v) => view.predict(slot, v)),
      bar("Column's lines", data.column_lines, view.max, "estimated"),
      bar("Lines fetched", null, view.max, "measured hidden", "hidden"),
    );
  } else {
    bars.append(
      bar("You predicted", predicted ?? null, view.max, "predicted", "no guess"),
      bar("Column's lines", data.column_lines, view.max, "estimated"),
      bar("Lines fetched", g.misses, view.max, "measured"),
    );
  }
  card.append(bars);
  if (!view.asking) {
    const flow = el("div", "plan-op-flow");
    for (const [label, field] of [["reads", "reads"], ["hits", "hits"], ["misses", "misses"], ["bytes fetched", "bytes_fetched"]]) {
      const b = el("b", "", fmt(g[field]));
      b.dataset.field = field;
      flow.append(el("span", "", label), " ", b, " ");
    }
    card.append(flow);
  }
  return card;
}

/**
 * Draw `data` into `root`. `ctx.store` keeps the reader's predictions and whether they revealed
 * the measurement, under `ctx.key`, so both survive a reload and a rerun in the browser.
 */
export function mountGather(root, data, ctx) {
  const saved = (() => {
    try { return JSON.parse(ctx.store.get(`${ctx.key}:predict`) || "null"); } catch { return null; }
  })() || { predictions: {}, revealed: false };
  const save = () => ctx.store.set(`${ctx.key}:predict`, JSON.stringify(saved));
  const redraw = () => { root.replaceChildren(); mountGather(root, data, ctx); };

  const asking = !saved.revealed;
  const guesses = Object.values(saved.predictions);
  // Before the reveal, scaled to the column's lines alone, so no bar's length hints at the answer.
  const max = Math.max(1, data.column_lines, ...(asking ? [] : [...data.gathers.map((g) => g.misses), ...guesses]));
  root.dataset.asking = String(asking);

  const head = el("div", "lab-head");
  const title = el("span", "lab-title");
  title.append("Gathering ", el("code", "", data.column), asking
    ? " into date order: predict the lines each gather fetches"
    : " into date order, as it ran");
  head.append(title);
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

  const facts = el("p", "gather-facts");
  facts.innerHTML = `<b data-field="rows"></b> rows of <code></code>, <b data-field="width"></b> bytes each:
    <b data-field="column_lines"></b> lines of <b data-field="line_bytes"></b> bytes. The cache holds
    <b data-field="lines"></b> lines.`;
  const put = (field, value) => { facts.querySelector(`[data-field="${field}"]`).textContent = fmt(value); };
  facts.querySelector("code").textContent = data.type;
  put("rows", data.rows);
  put("width", data.width);
  put("column_lines", data.column_lines);
  put("line_bytes", data.cache.line_bytes);
  put("lines", data.cache.lines);
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
  const runs = el("div", "gather-runs");
  data.gathers.forEach((g, i) => runs.append(run(g, data, view, i)));
  root.append(runs);

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
      "Type your prediction of each gather's lines fetched first, or reveal without guessing."));
    root.append(ask);
  }
}
