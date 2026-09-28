// The plan panel: DuckDB's operators as the rows flow through them, from query_lab.report.plan.
//
// It draws the tree top down, as DuckDB's EXPLAIN does. For the book's own query the panel asks
// first and answers second: each operator shows the planner's estimate, which EXPLAIN printed
// before the query ran, and a box for the reader's prediction of its output. The measurement
// stays hidden until the reader reveals it. Then each operator has three bars on one scale (your
// prediction, the planner's estimate, the measurement), its rows in and out, and the rows it
// passes up the link to the operator above.
//
// Every number drawn is a field of the report's JSON or a number the reader typed. Before the
// reveal the bars are scaled to the estimates alone, so their lengths give nothing away. A query
// the reader edited has nothing to predict against, and draws revealed.

const fmt = (n) => Number(n).toLocaleString("en-GB");

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** Every operator, top down, as the report lists them: the order predictions are kept in. */
function operators(node, out = []) {
  out.push(node);
  for (const c of node.children) operators(c, out);
  return out;
}

/** One bar; `value` null means there is no such number, and the bar says so. */
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

/** A place for the reader's prediction: a number box, kept as they type. */
function predictionBox(value, onInput) {
  const row = el("label", "plan-bar predicted plan-predict");
  row.append(el("span", "plan-bar-label", "You predict"));
  const input = el("input");
  input.type = "number";
  input.min = "0";
  input.step = "1";
  input.inputMode = "numeric";
  input.placeholder = "rows out";
  if (value !== undefined) input.value = String(value);
  input.addEventListener("input", () => onInput(input.value === "" ? undefined : Math.max(0, Math.round(Number(input.value)))));
  row.append(input);
  return row;
}

function operator(node, view) {
  const index = view.all.indexOf(node);
  const slot = `${index}:${node.operator}`;
  const box = el("div", "plan-node");
  const card = el("div", "plan-op");
  card.dataset.operator = node.operator;
  card.append(el("div", "plan-op-name", node.operator));
  if (node.detail.length) {
    const dl = el("dl", "plan-op-detail");
    for (const [key, ...values] of node.detail) {
      dl.append(el("dt", "", key), el("dd", "", values.join(", ")));
    }
    card.append(dl);
  }
  const bars = el("div", "plan-bars");
  const predicted = view.predictions[slot];
  if (view.asking) {
    bars.append(
      predictionBox(predicted, (v) => view.predict(slot, v)),
      bar("Estimated", node.estimated_rows_out, view.max, "estimated"),
      bar("Measured", null, view.max, "measured hidden", "hidden"),
    );
  } else {
    if (view.predicting) bars.append(bar("You predicted", predicted ?? null, view.max, "predicted", "no guess"));
    bars.append(
      bar("Estimated", node.estimated_rows_out, view.max, "estimated"),
      bar("Measured", node.rows_out, view.max, "measured"),
    );
  }
  card.append(bars);
  if (!view.asking) {
    const flow = el("div", "plan-op-flow");
    flow.innerHTML = `<span>rows in</span> <b data-field="rows_in"></b> <span>rows out</span> <b data-field="rows_out"></b>`;
    flow.querySelector('[data-field="rows_in"]').textContent = fmt(node.rows_in);
    flow.querySelector('[data-field="rows_out"]').textContent = fmt(node.rows_out);
    card.append(flow);
  }
  box.append(card);
  if (node.children.length) {
    const kids = el("div", "plan-children");
    for (const child of node.children) {
      const branch = el("div", "plan-branch");
      branch.append(el("div", "plan-link", view.asking ? "▲ rows" : `▲ ${fmt(child.rows_out)} rows`), operator(child, view));
      kids.append(branch);
    }
    box.append(kids);
  }
  return box;
}

/** The first rows of the result, as the report carried them. */
function preview(data) {
  const box = el("div", "plan-preview");
  const shown = data.preview.rows.length;
  box.append(el("h4", "", shown < data.result_rows
    ? `The first ${fmt(shown)} of ${fmt(data.result_rows)} result rows`
    : `The result: ${fmt(data.result_rows)} rows`));
  const table = el("table");
  const head = el("tr");
  for (const c of data.preview.columns) head.append(el("th", "", c));
  table.append(el("thead"), el("tbody"));
  table.tHead.append(head);
  for (const row of data.preview.rows) {
    const tr = el("tr");
    for (const v of row) {
      tr.append(el("td", typeof v === "number" ? "num" : "", v === null ? "NULL"
        : typeof v === "number" ? v.toLocaleString("en-GB", { maximumFractionDigits: 2 }) : String(v)));
    }
    table.tBodies[0].append(tr);
  }
  const wrap = el("div", "plan-preview-wrap");
  wrap.append(table);
  box.append(wrap);
  return box;
}

/**
 * Draw `data` into `root`. `ctx.store` keeps the reader's predictions and whether they revealed
 * the measurement, under `ctx.key`, so both survive a reload and a rerun in the browser.
 */
export function mountPlan(root, data, ctx) {
  const saved = (() => {
    try { return JSON.parse(ctx.store.get(`${ctx.key}:predict`) || "null"); } catch { return null; }
  })() || { predictions: {}, revealed: false };
  const save = () => ctx.store.set(`${ctx.key}:predict`, JSON.stringify(saved));
  const redraw = () => { root.replaceChildren(); mountPlan(root, data, ctx); };

  const all = operators(data.root);
  const predicting = !data.edited;
  const asking = predicting && !saved.revealed;
  const guesses = all.map((n, i) => saved.predictions[`${i}:${n.operator}`]).filter((v) => v !== undefined);
  // Before the reveal, scaled to the estimates alone, so a bar's length cannot hint at the answer.
  const max = Math.max(1, ...all.map((n) => n.estimated_rows_out ?? 0),
    ...(asking ? [] : [...all.map((n) => n.rows_out), ...guesses]));
  root.dataset.asking = String(asking);

  const head = el("div", "lab-head");
  head.append(el("span", "lab-title", data.edited ? "Your query's plan, as it ran"
    : asking ? "The plan: predict each operator's rows out" : "The plan, as it ran"));
  const note = el("span", "lab-note");
  note.append(data.edited ? "edited from " : "", el("code", "", `queries/${data.query}`));
  head.append(note);
  if (predicting && !asking) {
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

  const view = {
    all, max, asking, predicting,
    predictions: saved.predictions,
    predict(slot, value) {
      if (value === undefined) delete saved.predictions[slot];
      else saved.predictions[slot] = value;
      save();
    },
  };
  const tree = el("div", "plan-tree");
  tree.append(operator(data.root, view));
  root.append(tree);

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
      "Type your prediction of each operator's rows out first, or reveal without guessing."));
    root.append(ask);
  } else {
    root.append(preview(data));
  }
}
