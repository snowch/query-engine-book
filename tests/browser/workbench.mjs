// Every problems workbench in the built site, driven in headless Chromium.
//
//   node tests/browser/workbench.mjs _build/html
//
// The graders are the repository's own tests, run by pytest under Pyodide on what the reader
// wrote. This checks the page wires them up: the stubs as the book ships them fail every check
// with the stub's own NotImplementedError; an answer that runs but is wrong fails on the graders'
// assertions instead, so the page ran the reader's text; the text is kept in the browser's storage;
// and reset restores the stubs. (That a right answer passes is shown where the problems are
// written, at the book's build, and never committed.)

import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { ORIGIN, directory, launch, openPage } from "./chromium.mjs";

const site = resolve(process.argv[2] || "_build/html");
const pages = readdirSync(site).filter((f) => f.endsWith(".html")
  && readFileSync(join(site, f), "utf8").includes('class="workbench"'));
if (!pages.length) throw new Error(`no page in ${site} has a workbench`);

function check(ok, message) {
  if (!ok) throw new Error(message);
}

async function grade(page, wb) {
  await (await wb.$(".lab-run")).click();
  await page.waitForFunction((el) => el.dataset.ready !== "running" && el.querySelector(".wb-results").children.length,
    wb, { timeout: 600_000, polling: 500 });
  return wb.$$eval(".wb-problem li", (items) => items.map((li) => ({
    test: li.dataset.test, outcome: li.className, message: li.querySelector(".wb-message")?.textContent || "",
  })));
}

const browser = await launch();
let failures = 0;
try {
  for (const file of pages) {
    const page = await openPage(browser, directory(site));
    await page.goto(`${ORIGIN}/${file}`);
    const wb = await page.waitForSelector('.workbench[data-ready="true"]', { timeout: 30_000 });
    const chapter = await wb.getAttribute("data-chapter");
    try {
      const stubs = await wb.$eval("textarea", (t) => t.value);
      const shipped = await grade(page, wb);
      check(shipped.length > 0, "the graders reported nothing");
      check(shipped.every((t) => t.outcome === "failed" && t.message.startsWith("NotImplementedError")),
        `the stubs as shipped: ${JSON.stringify(shipped.find((t) => t.outcome !== "failed" || !t.message.startsWith("NotImplementedError")))}`);
      console.log(`  ${chapter}: the stubs fail every check (${shipped.length}) with their own NotImplementedError`);

      // An answer that runs and is wrong: every stub returns at once, having done nothing.
      const wrong = stubs.replace(/raise NotImplementedError\([^)]*\)/g, "return None");
      check(wrong !== stubs, "no stub to answer");
      await (await wb.$("textarea")).fill(wrong);
      const graded = await grade(page, wb);
      check(graded.some((t) => t.outcome === "failed" && !t.message.includes("NotImplementedError")),
        "the graders did not run the edited answer");
      const kept = await page.evaluate((c) => Object.keys(localStorage)
        .filter((k) => k.startsWith("problems:") && k.endsWith(`:${c}`)).map((k) => localStorage.getItem(k)), chapter);
      check(kept.length === 1 && kept[0] === wrong, "the answer was not kept in the browser's storage");
      await (await wb.$("button:not(.lab-run)")).click();
      check((await wb.$eval("textarea", (t) => t.value)) === stubs, "reset did not restore the stubs");
      console.log(`  ${chapter}: an edited answer is graded and kept, and reset restores the stubs`);
    } catch (error) {
      failures += 1;
      console.error(`FAILED ${file} ${chapter}: ${error.message}`);
    }
    await page.context().close();
  }
} finally {
  await browser.close();
}
if (failures) process.exit(1);
