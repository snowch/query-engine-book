// Every panel in the built site, driven in headless Chromium.
//
//   node tests/browser/panels.mjs _build/html
//
// For each page with a panel, the check reads the panel back from the page and holds it to the
// JSON the build embedded, which is query_lab.report's answer. Each experiment has a reader
// (PANELS below) that says what its drawing shows, asking and revealed:
//
// 1. It draws at once, asking: what the reader predicts from is shown, a box per prediction, and
//    every measurement hidden (for a plan, down to the rows on the links).
// 2. Predictions typed and revealed: every measurement is the JSON's, every prediction is what
//    was typed, and both survive a reload.
// 3. "Run it in your browser" reruns the report under Pyodide; the page must say the answer is
//    the build's and draw the same numbers.
// 4. An edited query draws what `python -m query_lab report … --sql` prints at a desk for the same
//    text; a broken one reports DuckDB's error; reset restores the book's query. "Predict again"
//    asks again.
// 5. Without JavaScript, the panel says it needs JavaScript.

import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { ORIGIN, directory, launch, openPage } from "./chromium.mjs";

const site = resolve(process.argv[2] || "_build/html");
const pages = readdirSync(site).filter((f) => f.endsWith(".html")
  && readFileSync(join(site, f), "utf8").includes('class="lab"'));
if (!pages.length) throw new Error(`no page in ${site} has a panel`);

/** The plan tree as the report wrote it, top down: what each drawn operator must show. */
function expected(node, out = []) {
  out.push({ operator: node.operator, estimated: node.estimated_rows_out, rows_in: node.rows_in, rows_out: node.rows_out, measured: node.rows_out });
  for (const c of node.children) expected(c, out);
  return out;
}

/** The plan tree as the page drew it, read back from the DOM. */
async function drawn(lab) {
  return lab.$$eval(".plan-op", (ops) => ops.map((op) => {
    const value = (s) => {
      const e = op.querySelector(s);
      if (!e) return undefined;
      const text = e.textContent;
      return text === "none" || text === "no guess" || text === "hidden" ? text : Number(text.replace(/,/g, ""));
    };
    const out = {
      operator: op.dataset.operator,
      estimated: value(".plan-bar.estimated .plan-bar-value"),
      rows_in: value('[data-field="rows_in"]'),
      rows_out: value('[data-field="rows_out"]'),
      measured: value(".plan-bar.measured .plan-bar-value"),
    };
    const predicted = value(".plan-bar.predicted .plan-bar-value");
    if (predicted !== undefined) out.predicted = predicted;
    return out;
  }));
}

const revealed = (want, guesses) => want.map((o, i) => ({ ...o, ...(guesses ? { predicted: guesses[i] } : {}) }));
const none = (v) => (v === null ? "none" : v);
const shown = (ops) => ops.map((o) => ({ ...o, estimated: none(o.estimated) }));

/** The gathers as the page drew them, read back from the DOM. */
async function drawnGathers(lab) {
  return lab.$$eval(".gather-run", (runs) => runs.map((run) => {
    const value = (s) => {
      const e = run.querySelector(s);
      if (!e) return undefined;
      const text = e.textContent;
      return text === "none" || text === "no guess" || text === "hidden" ? text : Number(text.replace(/,/g, ""));
    };
    const out = {
      fixture: run.dataset.fixture,
      column_lines: value(".plan-bar.estimated .plan-bar-value"),
      fetched: value(".plan-bar.measured .plan-bar-value"),
      dots: run.querySelectorAll(".gather-pattern circle").length,
    };
    for (const field of ["reads", "hits", "misses", "bytes_fetched"]) {
      const v = value(`[data-field="${field}"]`);
      if (v !== undefined) out[field] = v;
    }
    const predicted = value(".plan-bar.predicted .plan-bar-value");
    if (predicted !== undefined) out.predicted = predicted;
    return out;
  }));
}

/** For each experiment: how to read its drawing, and what it must show asking and revealed. */
const PANELS = {
  plan: {
    read: drawn,
    asking: (data) => shown(expected(data.root)).map((o) => ({ operator: o.operator, estimated: o.estimated, measured: "hidden" })),
    revealed: (data, guesses) => revealed(shown(expected(data.root)), guesses),
    count: (data) => expected(data.root).length,
  },
  gather: {
    read: drawnGathers,
    asking: (data) => data.gathers.map((g) => ({ fixture: g.fixture, column_lines: data.column_lines, fetched: "hidden", dots: g.pattern.length })),
    revealed: (data, guesses) => data.gathers.map((g, i) => ({
      fixture: g.fixture, column_lines: data.column_lines, fetched: g.misses, dots: g.pattern.length,
      reads: g.reads, hits: g.hits, misses: g.misses, bytes_fetched: g.bytes_fetched, predicted: guesses[i],
    })),
    count: (data) => data.gathers.length,
  },
};

function same(label, got, want) {
  const a = JSON.stringify(got), b = JSON.stringify(want);
  if (a !== b) throw new Error(`${label}: drew ${a}, expected ${b}`);
}

/** What a desk's query_lab.report returns for `config`, with an edited query's text. */
function desk(config, sql) {
  const out = execFileSync("python3", ["-m", "query_lab", "report", config.experiment, config.query, "--sql", sql], {
    env: { ...process.env, PYTHONPATH: "python:external/parquet-book/python" },
  });
  return JSON.parse(out);
}

const EDITED = "SELECT status, count(*) AS orders\nFROM 'fixtures/orders-sorted.parquet'\n"
  + "WHERE amount > 500\nGROUP BY status\nORDER BY status;";

async function runAndWait(page, lab) {
  await (await lab.$(".lab-run")).click();
  await page.waitForFunction((el) => el.dataset.ready === "true" || el.dataset.ready === "error", lab,
    { timeout: 300_000, polling: 200 });
}

async function ready(page) {
  await page.waitForFunction(() => [...document.querySelectorAll(".lab")].every((l) => l.dataset.ready === "true"),
    null, { timeout: 10_000 });
}

async function checkPanel(page, file, index) {
  const lab = () => page.$$(".lab[data-experiment]").then((all) => all[index]);
  let el = await lab();
  const experiment = await el.getAttribute("data-experiment");
  const label = `${file} ${experiment}`;
  const panel = PANELS[experiment];
  if (!panel) throw new Error(`${label}: no reader for this experiment in tests/browser/panels.mjs`);
  const data = JSON.parse(await el.$eval("script.lab-data", (s) => s.textContent));
  const config = { experiment, query: await el.getAttribute("data-query") };
  const read = panel.read;

  // 1. Asking.
  same(`${label}, asking`, await read(el), panel.asking(data));
  const links = await el.$$eval(".plan-link", (ls) => ls.map((l) => l.textContent));
  if (links.some((t) => /\d/.test(t))) throw new Error(`${label}: a link gives away rows before the reveal: ${links}`);
  if (await el.$(".plan-preview")) throw new Error(`${label}: the result shows before the reveal`);

  // 2. Predict, reveal, reload.
  const inputs = await el.$$(".plan-predict input");
  const count = panel.count(data);
  if (inputs.length !== count) throw new Error(`${label}: ${inputs.length} prediction boxes for ${count} predictions`);
  const guesses = [...Array(count).keys()].map((i) => 1000 + 111 * i);
  for (const [i, input] of inputs.entries()) await input.fill(String(guesses[i]));
  await (await el.$(".plan-reveal")).click();
  same(`${label}, revealed`, await read(el), panel.revealed(data, guesses));
  await page.reload();
  await ready(page);
  el = await lab();
  same(`${label}, after a reload`, await read(el), panel.revealed(data, guesses));
  console.log(`  ${label}: asks first, reveals the build's numbers beside the predictions, and keeps both`);

  // 3. The same report, in the browser.
  await runAndWait(page, el);
  const [agrees, status] = await el.evaluate((e) => [e.dataset.agrees, e.querySelector(".lab-status").textContent]);
  if (agrees !== "true") throw new Error(`${label}: ${status}`);
  same(`${label}, from your browser`, await read(el), panel.revealed(data, guesses));
  console.log(`  ${label}: recomputed in the browser to the build's answer`);

  // 4. Edited, broken, reset, predict again.
  const editor = await el.$(".lab-editor textarea");
  if (editor) {
    await (await el.$(".lab-editor summary")).click();
    await editor.fill(EDITED);
    await runAndWait(page, el);
    const edited = await el.$eval(".lab-status", (s) => s.textContent);
    if (!edited.startsWith("Your query")) throw new Error(`${label}, edited: ${edited}`);
    const theirs = desk(config, EDITED);
    same(`${label}, edited`, await drawn(el), shown(expected(theirs.root)));
    const rows = await el.$$eval(".plan-preview tbody tr", (trs) => trs.map((tr) => [...tr.cells].map((c) => c.textContent)));
    same(`${label}, edited result`, rows, theirs.preview.rows.map((r) => r.map((v) =>
      typeof v === "number" ? v.toLocaleString("en-GB", { maximumFractionDigits: 2 }) : String(v))));
    // Kept under a key named for this book (the site's directory), since other books share the origin.
    const kept = await page.evaluate((suffix) => Object.keys(localStorage)
      .filter((k) => k.startsWith("lab:") && k.endsWith(suffix)).map((k) => localStorage.getItem(k)),
    `:${config.experiment}:${config.query}`);
    if (kept.length !== 1 || kept[0] !== EDITED) {
      throw new Error(`${label}: the edit was not kept in the browser's storage`);
    }
    console.log(`  ${label}: an edited query, run in the browser, draws what a desk computes for it`);

    await editor.fill("SELECT nothing FROM nowhere");
    await runAndWait(page, el);
    const broken = await el.$eval(".lab-status", (s) => s.textContent);
    if (!broken.startsWith("DuckDB could not run your query") || (await drawn(el)).length === 0) {
      throw new Error(`${label}, broken query: ${broken}`);
    }
    await (await el.$(".lab-reset")).click();
    same(`${label}, after reset`, await drawn(el), panel.revealed(data, guesses));
    if (await editor.inputValue() !== data.source) throw new Error(`${label}: reset did not restore the query`);
    console.log(`  ${label}: a broken query reports DuckDB's error, and reset restores the book's query`);
  }
  await (await el.$(".plan-again")).click();
  same(`${label}, predicting again`, await read(el), panel.asking(data));
  if ((await el.$$eval(".plan-predict input", (is) => is.map((i) => i.value))).some(Boolean)) {
    throw new Error(`${label}: predicting again kept the old predictions`);
  }
  return { label };
}

const browser = await launch();
let failures = 0;
try {
  for (const file of pages) {
    const page = await openPage(browser, directory(site));
    await page.goto(`${ORIGIN}/${file}`);
    await ready(page);
    const count = (await page.$$(".lab[data-experiment]")).length;
    for (let i = 0; i < count; i++) {
      try {
        const { label } = await checkPanel(page, file, i);
        // 5. No JavaScript.
        const bare = await openPage(browser, directory(site), { javaScriptEnabled: false });
        await bare.goto(`${ORIGIN}/${file}`);
        const notice = await (await bare.$$(".lab[data-experiment]"))[i].evaluate((e) => e.textContent.trim());
        await bare.context().close();
        if (!notice.endsWith("This panel needs JavaScript.")) throw new Error(`${label}, without JavaScript: ${notice}`);
        console.log(`  ${label}: without JavaScript, says it needs it`);
      } catch (error) {
        failures += 1;
        console.error(`FAILED ${file} panel ${i}: ${error.message}`);
      }
    }
    await page.context().close();
  }
} finally {
  await browser.close();
}
if (failures) process.exit(1);
