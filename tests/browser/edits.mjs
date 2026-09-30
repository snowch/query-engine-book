// Every editable listing in the built site, driven in headless Chromium.
//
//   node tests/browser/edits.mjs _build/html
//
// A listing of the engine that a `run` block follows: run as the book quotes it, under Pyodide,
// it must give the build's answer (a panel's report, compared with the build's JSON) or pass the
// engine's tests the block names. An edit that does not parse must say so, with the line of the
// edit it failed on, and a run after it must give the build's answer again: the edit was undone.
// The edit is kept in the browser's storage, and reopens its editor on a reload. A block that
// shows a plan must draw its rows and counters as a desk computes them.
//
// A listing over thirty lines is folded, with a button that shows the rest.
//
// A quoted query, the first on each page: an edited query must draw what a desk's report prints
// for the same text, and mark every figure and panel computed for the book's query as the book's,
// until reset; a broken one must report DuckDB's error.

import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { ORIGIN, directory, launch, openPage } from "./chromium.mjs";

const site = resolve(process.argv[2] || "_build/html");
// ONLY=<part of a file name> checks one page, while working on it.
const pages = readdirSync(site).filter((f) => f.endsWith(".html") && readFileSync(join(site, f), "utf8").includes('class="quoted"')
  && (!process.env.ONLY || f.includes(process.env.ONLY)));

function check(ok, message) {
  if (!ok) throw new Error(message);
}

async function run(page, figure) {
  const result = await figure.evaluateHandle((f) => f.nextElementSibling);
  await (await figure.$(".edit-bar .lab-run")).click();
  await page.waitForFunction((r) => r.dataset.ready === "true" || r.dataset.ready === "error", result,
    { timeout: 600_000, polling: 250 });
  return result.evaluate((r) => ({
    ready: r.dataset.ready, agrees: r.dataset.agrees, passed: r.dataset.passed, total: r.dataset.total,
    status: r.querySelector(".lab-status").textContent,
    operators: [...r.querySelectorAll(".plan-op")].map((op) => op.dataset.operator),
    // What the page drew of the plan a run block shows, and which plan the block names.
    shown: r.querySelector(".edit-shown")?.dataset.shown ?? null,
    show: (() => {
      const s = r.nextElementSibling;
      return s && s.matches("script.run-then") ? (JSON.parse(s.textContent).tests || {}).show || null : null;
    })(),
  }));
}

/** What a plan returns and counts at a desk, as a run block shows it in the page. */
function deskShown(query) {
  const code = "import json, sys; from pathlib import Path; from query_lab.edits import shown; "
    + "print(json.dumps(shown(Path('.'), sys.argv[1])))";
  const out = execFileSync("python3", ["-c", code, query], {
    env: { ...process.env, PYTHONPATH: "python:external/parquet-book/python" },
  });
  return JSON.stringify(JSON.parse(out.toString()));
}

function desk(query, sql) {
  const out = execFileSync("python3", ["-m", "query_lab", "report", "plan", query, "--sql", sql], {
    env: { ...process.env, PYTHONPATH: "python:external/parquet-book/python" },
  });
  return JSON.parse(out);
}

function operators(node, out = []) {
  out.push(node.operator);
  for (const c of node.children) operators(c, out);
  return out;
}

const EDITED = "SELECT status, count(*) AS orders\nFROM 'fixtures/orders-sorted.parquet'\nGROUP BY status\nORDER BY status;";

/** Open `file` afresh, and the `index`th editable listing on it once the page has mounted them. */
async function open(page, file, index) {
  await page.goto(`${ORIGIN}/${file}`);
  await page.waitForFunction((i) => document.querySelectorAll("figure.quoted[data-editable]").length > i, index, { timeout: 10_000 });
  return (await page.$$("figure.quoted[data-editable]"))[index];
}

const browser = await launch();
let failures = 0;
let checked = 0;
try {
  for (const file of pages) {
    const page = await openPage(browser, directory(site));
    await page.goto(`${ORIGIN}/${file}`);
    await page.waitForLoadState("load");
    // A listing over thirty lines is folded, and its button shows the rest.
    const folds = await page.$$eval("#main figure.quoted", (fs) => fs.map((f) => {
      const lines = f.querySelector(":scope > pre").textContent.replace(/\n$/, "").split("\n").length;
      return [lines > 30, f.dataset.folded === "true", !!f.querySelector(":scope > .fold-toggle")];
    }));
    if (folds.some(([long, folded, button]) => long !== folded || long !== button)) {
      failures += 1;
      console.error(`FAILED ${file}: a long listing is not folded, or a short one is`);
    }
    const first = await page.$('#main figure.quoted[data-folded="true"]');
    if (first) {
      await (await first.$(".fold-toggle")).click();
      if (await first.getAttribute("data-folded") !== "false") {
        failures += 1;
        console.error(`FAILED ${file}: the fold's button did not show the rest`);
      } else {
        console.log(`  ${file}: long listings fold, and a button shows the rest`);
      }
    }
    const kinds = await page.$$eval("figure.quoted[data-editable]", (fs) => fs.map((f) => [f.dataset.editable, f.dataset.file]));
    // Every listing of the engine, and the first query on the page.
    const firstQuery = kinds.findIndex(([kind]) => kind === "query");
    for (const [index, [kind, name]] of kinds.entries()) {
      if (kind === "query" && index !== firstQuery) continue;
      const label = `${file} ${name}`;
      try {
        let figure = await open(page, file, index);
        await (await figure.$(".edit-open")).click();
        const editor = await figure.$("textarea.code-area");
        const listing = await editor.inputValue();
        if (kind === "query") {
          await editor.fill(EDITED);
          const got = await run(page, figure);
          check(got.ready === "true" && got.status.startsWith("Your query"), `${label}, edited: ${got.status}`);
          const want = operators(desk(name.slice("queries/".length), EDITED).root);
          check(JSON.stringify(got.operators) === JSON.stringify(want), `${label}: drew ${got.operators}, the desk ${want}`);
          // Every figure and panel computed for the book's query now says so, and reset clears it.
          const tagged = await page.$$eval(`#main [data-query="${name.slice("queries/".length)}"]`,
            (els) => els.map((e) => e.dataset.stale === "true" && !!e.querySelector(":scope > .stale-note")));
          check(tagged.every(Boolean), `${label}: ${tagged.filter((t) => !t).length} of the book's figures were not marked`);
          await editor.fill("SELECT nothing FROM nowhere");
          const broken = await run(page, figure);
          check(broken.ready === "error" && broken.status.startsWith("DuckDB could not run your query"), `${label}, broken: ${broken.status}`);
          await (await figure.$(".edit-reset")).click();
          check(await page.$$eval("#main [data-stale]", (els) => els.length) === 0, `${label}: reset left figures marked`);
          console.log(`  ${label}: an edited query draws the desk's plan, marks the book's figures, and a broken one DuckDB's error`);
        } else {
          const shipped = await run(page, figure);
          check(shipped.ready === "true", `${label}, as the book quotes it: ${shipped.status}`);
          const right = (r) => (r.total !== undefined ? r.passed === r.total && Number(r.total) > 0 : r.agrees === "true");
          check(right(shipped), `${label}: ${shipped.status}`);
          if (shipped.show) {
            check(shipped.shown && JSON.stringify(JSON.parse(shipped.shown)) === deskShown(shipped.show),
              `${label}: the plan it shows differs from the desk's: ${shipped.shown}`);
          }
          await editor.fill(`${listing}\n(`);
          const broken = await run(page, figure);
          check(broken.ready === "error" && /(Syntax|Indentation)Error: .*\(line \d+ of your edit\)$/.test(broken.status), `${label}, broken: ${broken.status}`);
          // Kept, and reopened on a reload.
          figure = await open(page, file, index);
          check(await figure.getAttribute("data-editing") === "true", `${label}: a kept edit did not reopen its editor`);
          check(await figure.$eval("textarea.code-area", (t) => t.value) === `${listing}\n(`, `${label}: the edit was not kept`);
          await (await figure.$(".edit-reset")).click();
          const restored = await run(page, figure);
          check(restored.ready === "true" && right(restored), `${label}, after a broken edit and a reset: ${restored.status}`);
          await (await figure.$(".edit-open")).click();
          check(!(await figure.$("textarea.code-area")), `${label}: closing the editor left it open`);
          const also = shipped.show ? `, shows ${shipped.show}'s plan as a desk runs it` : "";
          console.log(`  ${label}: as quoted it gives the build's answer${also}; a broken edit says where, and is undone`);
        }
        checked += 1;
      } catch (error) {
        failures += 1;
        console.error(`FAILED ${label}: ${error.message}`);
      }
    }
    await page.context().close();
  }
} finally {
  await browser.close();
}
if (!checked) {
  console.error("FAILED: no editable listing was checked");
  process.exit(1);
}
if (failures) process.exit(1);
