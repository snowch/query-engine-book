// Every panel in the built site, driven in headless Chromium.
//
//   node tests/browser/panels.mjs _build/html
//
// For each page with a panel, the check reads the panel back from the page and holds it to the
// JSON the build embedded, which is query_lab.report's answer:
//
// 1. It draws at once, asking: estimates shown, a box per operator for a prediction, and every
//    measurement hidden, down to the rows on the links.
// 2. Predictions typed and revealed: every measurement is the JSON's, every prediction is what
//    was typed, and both survive a reload.
// 3. "Run it in your browser" reruns the report under Pyodide; the page must say the answer is
//    the build's and draw the same numbers.
// 4. An edited query draws what `python -m query_lab report … --sql` prints at a desk for the same
//    text; a broken one reports DuckDB's error; reset restores the book's query. "Predict again"
//    asks again.
// 5. Without JavaScript, and in print, the panel is a table of the same numbers.

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
  const label = `${file} ${await el.getAttribute("data-experiment")}`;
  const data = JSON.parse(await el.$eval("script.lab-data", (s) => s.textContent));
  const config = { experiment: await el.getAttribute("data-experiment"), query: await el.getAttribute("data-query") };
  const want = shown(expected(data.root));

  // 1. Asking.
  const asking = await drawn(el);
  same(`${label}, asking`, asking, want.map((o) => ({ operator: o.operator, estimated: o.estimated, measured: "hidden" })));
  const links = await el.$$eval(".plan-link", (ls) => ls.map((l) => l.textContent));
  if (links.some((t) => /\d/.test(t))) throw new Error(`${label}: a link gives away rows before the reveal: ${links}`);
  if (await el.$(".plan-preview")) throw new Error(`${label}: the result shows before the reveal`);

  // 2. Predict, reveal, reload.
  const inputs = await el.$$(".plan-predict input");
  if (inputs.length !== want.length) throw new Error(`${label}: ${inputs.length} prediction boxes for ${want.length} operators`);
  const guesses = want.map((_, i) => 1000 + 111 * i);
  for (const [i, input] of inputs.entries()) await input.fill(String(guesses[i]));
  await (await el.$(".plan-reveal")).click();
  same(`${label}, revealed`, await drawn(el), revealed(want, guesses));
  await page.reload();
  await ready(page);
  el = await lab();
  same(`${label}, after a reload`, await drawn(el), revealed(want, guesses));
  console.log(`  ${label}: asks first, reveals the build's numbers beside the predictions, and keeps both`);

  // 3. The same report, in the browser.
  await runAndWait(page, el);
  const [agrees, status] = await el.evaluate((e) => [e.dataset.agrees, e.querySelector(".lab-status").textContent]);
  if (agrees !== "true") throw new Error(`${label}: ${status}`);
  same(`${label}, from your browser`, await drawn(el), revealed(want, guesses));
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
    if (await page.evaluate((k) => localStorage.getItem(k), `lab:${config.experiment}:${config.query}`) !== EDITED) {
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
    same(`${label}, after reset`, await drawn(el), revealed(want, guesses));
    if (await editor.inputValue() !== data.source) throw new Error(`${label}: reset did not restore the query`);
    console.log(`  ${label}: a broken query reports DuckDB's error, and reset restores the book's query`);
  }
  await (await el.$(".plan-again")).click();
  same(`${label}, predicting again`, await drawn(el), want.map((o) => ({ operator: o.operator, estimated: o.estimated, measured: "hidden" })));
  if ((await el.$$eval(".plan-predict input", (is) => is.map((i) => i.value))).some(Boolean)) {
    throw new Error(`${label}: predicting again kept the old predictions`);
  }
  return { label, want };
}

/** The fallback table, read back: operator, rows in, estimate, measured. */
async function table(el) {
  return el.$$eval(".lab-fallback tbody tr", (trs) => trs.map((tr) => {
    const [operator, rowsIn, estimated, measured] = [...tr.cells].map((c) => c.textContent);
    const n = (t) => (t === "none" ? "none" : Number(t.replace(/,/g, "")));
    return { operator, estimated: n(estimated), rows_in: n(rowsIn), rows_out: n(measured), measured: n(measured) };
  }));
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
        const { label, want } = await checkPanel(page, file, i);
        // 5. Print, and no JavaScript.
        await page.emulateMedia({ media: "print" });
        const el = (await page.$$(".lab[data-experiment]"))[i];
        const printed = await el.evaluate((e) => [getComputedStyle(e.querySelector(".lab-fallback")).display,
          getComputedStyle(e.querySelector(".lab-body")).display]);
        if (printed[0] === "none" || printed[1] !== "none") throw new Error(`${label}: print shows ${printed}`);
        await page.emulateMedia({ media: "screen" });
        const bare = await openPage(browser, directory(site), { javaScriptEnabled: false });
        await bare.goto(`${ORIGIN}/${file}`);
        const plain = (await bare.$$(".lab[data-experiment]"))[i];
        same(`${label}, without JavaScript`, await table(plain), want.map((o) => ({ ...o })));
        await bare.context().close();
        console.log(`  ${label}: without JavaScript and in print, the same numbers as a table`);
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
