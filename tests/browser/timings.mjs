// Every timed block in the built site, timed in headless Chromium.
//
//   node tests/browser/timings.mjs _build/html
//
// Before the reader asks, a timed block shows its cases and no time: the page holds none. Pressed,
// it times every case under Pyodide and draws how long each took, and says where it was timed. A
// case whose timing returns a profile draws where the time went, operator by operator. Whether
// the times come out in the order a chapter says is python/tests/test_timing.py's to check, at a
// desk: a browser on a shared CI machine is too noisy to hold to it.

import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { ORIGIN, directory, launch, openPage } from "./chromium.mjs";

const site = resolve(process.argv[2] || "_build/html");
const pages = readdirSync(site).filter((f) => f.endsWith(".html") && readFileSync(join(site, f), "utf8").includes('class="timed"')
  && (!process.env.ONLY || f.includes(process.env.ONLY)));

const browser = await launch();
let failures = 0;
let checked = 0;
try {
  for (const file of pages) {
    const page = await openPage(browser, directory(site));
    await page.goto(`${ORIGIN}/${file}`);
    await page.waitForFunction(() => [...document.querySelectorAll(".timed")].every((b) => b.dataset.ready), null, { timeout: 10_000 });
    for (const block of await page.$$(".timed")) {
      const of = await block.getAttribute("data-of");
      const label = `${file} ${of}`;
      try {
        const before = await block.$$eval(".timed-value", (vs) => vs.map((v) => v.textContent));
        if (!before.length || before.some((v) => v !== "not timed yet")) throw new Error(`before timing, it showed ${before}`);
        await (await block.$(".lab-run")).click();
        await page.waitForFunction((b) => b.dataset.ready === "true" || b.dataset.ready === "error", block,
          { timeout: 900_000, polling: 500 });
        const got = await block.evaluate((b) => ({
          ready: b.dataset.ready,
          status: b.querySelector(".lab-status").textContent,
          cases: [...b.querySelectorAll(".timed-case")].map((c) => ({
            label: c.dataset.case, seconds: Number(c.dataset.seconds), shown: c.querySelector(".timed-value").textContent,
            profile: c.querySelectorAll(".timed-op").length,
          })),
        }));
        if (got.ready !== "true") throw new Error(got.status);
        if (!got.status.startsWith("Timed in your browser")) throw new Error(`it said ${got.status}`);
        for (const c of got.cases) {
          if (!(c.seconds > 0) || !/ (ms|s) · /.test(c.shown)) throw new Error(`${c.label} shows ${c.shown}`);
        }
        if (of === "two_engines" && got.cases.some((c) => c.profile === 0)) throw new Error("a profile was not drawn");
        console.log(`  ${label}: ${got.cases.map((c) => `${c.label} ${c.shown}`).join("; ")}`);
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
  console.error("FAILED: no timed block was checked");
  process.exit(1);
}
if (failures) process.exit(1);
