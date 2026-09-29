// The plan panel: DuckDB's operators as the rows flow through them, from query_lab.report.plan.
//
// It draws the tree top down, as DuckDB's EXPLAIN does. Each operator shows two bars on one
// scale: the planner's estimate, which EXPLAIN printed before the query ran, and what the profile
// measured. Under them, its rows in and out, and on the link to the operator above, the rows it
// passed up.
//
// A report can carry variants: changes to the query the book computed when it was built. The panel
// offers each as a button and redraws from that variant's report at once, so a reader sees which
// numbers move when the query changes, and which do not, with nothing to download. A query the
// reader edits runs in the browser instead (lab.js), and draws the same way.
//
// Every number drawn is a field of the report's JSON.

const fmt = (n) => Number(n).toLocaleString("en-GB");

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** One bar; `value` null means there is no such number, and the bar says so. */
function bar(label, value, max, kind) {
  const row = el("div", `plan-bar ${kind}`);
  row.append(el("span", "plan-bar-label", label));
  const track = el("span", "plan-bar-track");
  const fill = el("span", "plan-bar-fill");
  fill.style.width = `${max && value !== null ? Math.min(100, (100 * value) / max) : 0}%`;
  track.append(fill);
  row.append(track, el("span", "plan-bar-value", value === null ? "none" : fmt(value)));
  return row;
}

/** Every operator, top down, as the report lists them. */
function operators(node, out = []) {
  out.push(node);
  for (const c of node.children) operators(c, out);
  return out;
}

function operator(node, max) {
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
  bars.append(
    bar("Estimated", node.estimated_rows_out, max, "estimated"),
    bar("Measured", node.rows_out, max, "measured"),
  );
  card.append(bars);
  const flow = el("div", "plan-op-flow");
  flow.innerHTML = `<span>rows in</span> <b data-field="rows_in"></b> <span>rows out</span> <b data-field="rows_out"></b>`;
  flow.querySelector('[data-field="rows_in"]').textContent = fmt(node.rows_in);
  flow.querySelector('[data-field="rows_out"]').textContent = fmt(node.rows_out);
  card.append(flow);
  box.append(card);
  if (node.children.length) {
    const kids = el("div", "plan-children");
    for (const child of node.children) {
      const branch = el("div", "plan-branch");
      branch.append(el("div", "plan-link", `▲ ${fmt(child.rows_out)} rows`), operator(child, max));
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

/** The query as it ran, without its comments: what a variant changed is there to read. */
function sql(source) {
  const text = source.split("\n").filter((l) => !l.trim().startsWith("--")).join("\n").trim();
  return el("pre", "plan-sql", text);
}

/** Draw `data` into `root`: the book's query, or one of its variants the reader picked. */
export function mountPlan(root, data, ctx, chosen = 0) {
  const choices = [data, ...(data.variants || [])];
  const shown = choices[chosen] || data;
  const all = operators(shown.root);
  const max = Math.max(1, ...all.map((n) => n.estimated_rows_out ?? 0), ...all.map((n) => n.rows_out));

  const head = el("div", "lab-head");
  head.append(el("span", "lab-title", data.edited ? "Your query's plan, as it ran"
    : "The plan: what DuckDB estimated, and what it measured"));
  const note = el("span", "lab-note");
  note.append(data.edited ? "edited from " : "", el("code", "", `queries/${shown.query}`));
  head.append(note);
  root.append(head);

  if (choices.length > 1) {
    const picker = el("div", "plan-variants");
    picker.append(el("span", "plan-variants-label", "Try a change:"));
    choices.forEach((choice, i) => {
      const b = el("button", "plan-variant", i === 0 ? "The book's query" : choice.label);
      b.type = "button";
      b.dataset.query = choice.query;
      b.setAttribute("aria-pressed", String(i === chosen));
      b.addEventListener("click", () => {
        root.replaceChildren();
        mountPlan(root, data, ctx, i);
      });
      picker.append(b);
    });
    root.append(picker);
    if (chosen > 0) root.append(sql(shown.source));
  }
  root.dataset.showing = shown.query;

  const tree = el("div", "plan-tree");
  tree.append(operator(shown.root, max));
  root.append(tree, preview(shown));
}
