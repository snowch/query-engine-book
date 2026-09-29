// The pruning panel: a query's scan, its filters pushed down, run against the orders file stored
// in date order and against the shuffled one, from query_lab.report.pruning.
//
// It asks first and answers second, as the other panels do. Each file shows the range of values
// the filters let through, on the scale of the file's values, the number of units in the file
// (row groups, or pages where the scan reads the page index), and a box for the reader's
// prediction of the units the scan reads. The measurement stays hidden until the reader reveals
// it. Then each unit is drawn as the range its statistics record, marked read or skipped with the
// reason, and under them the scan's counters.
//
// Every number drawn is a field of the report's JSON or a number the reader typed. Positions on
// the scale come from the report's values; nothing here counts.

const fmt = (n) => Number(n).toLocaleString("en-GB");

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** A unit's name, capitalised and plural, for a bar's label: "Row groups", "Pages". */
const plural = (unit) => `${unit[0].toUpperCase()}${unit.slice(1)}s`;

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
  input.placeholder = "read";
  if (value !== undefined) input.value = String(value);
  input.addEventListener("input", () => onInput(input.value === "" ? undefined : Math.max(0, Math.round(Number(input.value)))));
  row.append(input);
  return row;
}

/** The scale every range of one file is drawn on: from its smallest recorded value to its largest. */
function scale(file, windowRange) {
  const lows = file.units.map((g) => g.min);
  const highs = file.units.map((g) => g.max);
  const low = Math.min(...lows, ...(windowRange.min === null ? [] : [windowRange.min]));
  const high = Math.max(...highs, ...(windowRange.max === null ? [] : [windowRange.max]));
  const span = Math.max(1e-9, high - low);
  return (v) => `${(100 * (v - low)) / span}%`;
}

/** A span from `a` to `b` on the scale, as an absolutely placed element. */
function span(className, a, b, at) {
  const s = el("span", className);
  s.style.left = at(a);
  s.style.width = `calc(${at(b)} - ${at(a)})`;
  return s;
}

/** The filters' range, as a band across the track: open at an end no filter bounds. */
function windowBand(data, file, at) {
  const w = data.window;
  const lows = file.units.map((g) => g.min);
  const highs = file.units.map((g) => g.max);
  return span("pruning-window", w.min ?? Math.min(...lows), w.max ?? Math.max(...highs), at);
}

function rowGroups(data, file, at) {
  const list = el("ol", "pruning-groups");
  list.start = 0;
  for (const g of file.units) {
    const item = el("li", `pruning-group ${g.read ? "read" : "skipped"}`);
    item.dataset.read = String(g.read);
    item.title = `${g.min_label} to ${g.max_label}: ${g.read ? "read" : "skipped"}. ${g.why}.`;
    const track = el("span", "pruning-track");
    track.append(windowBand(data, file, at), span("pruning-range", g.min, g.max, at));
    item.append(track, el("span", "pruning-verdict", g.read ? "read" : "skipped"));
    list.append(item);
  }
  return list;
}

/** The ends of the file's scale, labelled with its smallest and largest recorded value. */
function axis(file) {
  const lowest = file.units.reduce((a, g) => (g.min < a.min ? g : a));
  const highest = file.units.reduce((a, g) => (g.max > a.max ? g : a));
  const row = el("div", "pruning-axis");
  row.append(el("span", "", lowest.min_label), el("span", "", highest.max_label));
  return row;
}

function fileCard(file, data, view, index) {
  const slot = `${index}:${file.fixture}`;
  const card = el("div", "plan-op pruning-file");
  card.dataset.fixture = file.fixture;
  const name = el("div", "plan-op-name");
  name.append("From ", el("code", "", file.fixture), file.label ? `, ${file.label}` : "");
  card.append(name);
  const at = scale(file, data.window);
  if (view.asking) {
    const track = el("div", "pruning-track pruning-track-alone");
    track.append(windowBand(data, file, at));
    card.append(track, axis(file), el("p", "pruning-caption", `The band: the ${data.column} values the filters let through, on the scale of the file's values.`));
  } else {
    card.append(rowGroups(data, file, at), axis(file));
    card.append(el("p", "pruning-caption", `Each ${file.unit}'s range of ${data.column}, from its statistics, and the filters' band across it.`));
  }
  const bars = el("div", "plan-bars");
  const predicted = view.predictions[slot];
  const total = file.units.length;
  if (view.asking) {
    bars.append(
      predictionBox(predicted, (v) => view.predict(slot, v)),
      bar(plural(file.unit), total, total, "estimated"),
      bar("Read", null, total, "measured hidden", "hidden"),
    );
  } else {
    bars.append(
      bar("You predicted", predicted ?? null, Math.max(total, predicted ?? 0), "predicted", "no guess"),
      bar(plural(file.unit), total, Math.max(total, predicted ?? 0), "estimated"),
      bar("Read", file.units_read, Math.max(total, predicted ?? 0), "measured"),
    );
    const flow = el("div", "plan-op-flow");
    for (const [label, field] of [["rows decoded", "rows_decoded"], ["rows handed up", "rows_out"],
      ["bytes read", "bytes_read"], ["requests", "requests"]]) {
      const b = el("b", "", fmt(file[field]));
      b.dataset.field = field;
      flow.append(el("span", "", label), " ", b, " ");
    }
    card.append(bars, flow);
    return card;
  }
  card.append(bars);
  return card;
}

/**
 * Draw `data` into `root`. `ctx.store` keeps the reader's predictions and whether they revealed
 * the measurement, under `ctx.key`, so both survive a reload and a rerun in the browser.
 */
export function mountPruning(root, data, ctx) {
  const saved = (() => {
    try { return JSON.parse(ctx.store.get(`${ctx.key}:predict`) || "null"); } catch { return null; }
  })() || { predictions: {}, revealed: false };
  const save = () => ctx.store.set(`${ctx.key}:predict`, JSON.stringify(saved));
  const redraw = () => { root.replaceChildren(); mountPruning(root, data, ctx); };
  const asking = !saved.revealed;
  root.dataset.asking = String(asking);

  const head = el("div", "lab-head");
  head.append(el("span", "lab-title", asking
    ? "The scan, filters pushed down: predict what it reads of each file"
    : "The scan, filters pushed down, as it ran"));
  const note = el("span", "lab-note");
  note.append(el("code", "", `queries/${data.query}`));
  head.append(note);
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
  facts.append("The scan tests ");
  data.filters.forEach((f, i) => facts.append(i ? " and " : "", el("code", "", f)));
  facts.append(", and hands up the rows that pass. The same query runs against both files.");
  root.append(facts);

  const view = {
    asking,
    predictions: saved.predictions,
    predict(slot, value) {
      if (value === undefined) delete saved.predictions[slot];
      else saved.predictions[slot] = value;
      save();
    },
  };
  const files = el("div", "gather-runs");
  data.files.forEach((f, i) => files.append(fileCard(f, data, view, i)));
  root.append(files);

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
      "Type your prediction of the units each scan reads first, or reveal without guessing."));
    root.append(ask);
  }
}
