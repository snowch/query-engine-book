// Every panel in the built site, driven in headless Chromium.
//
//   node tests/browser/panels.mjs _build/html
//
// For each page with a panel: the panel draws from the build's JSON with nothing downloaded, and
// every number it draws is a field of that JSON. Then the check presses "Run it in your browser",
// which runs the same report under Pyodide, and requires the page to say the answer is the build's
// and to draw the same numbers. A panel is a picture of query_lab.report; this is what holds it to
// that.

import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { ORIGIN, directory, launch, openPage } from "./chromium.mjs";

const site = resolve(process.argv[2] || "_build/html");
const pages = readdirSync(site).filter((f) => f.endsWith(".html")
  && readFileSync(join(site, f), "utf8").includes('class="lab"'));
if (!pages.length) throw new Error(`no page in ${site} has a panel`);

/** The plan tree as the report wrote it, top down: what each drawn operator must show. */
function expected(node, out = []) {
  out.push({ operator: node.operator, estimated: node.estimated_rows_out, rows_in: node.rows_in, rows_out: node.rows_out });
  for (const c of node.children) expected(c, out);
  return out;
}

/** The plan tree as the page drew it, read back from the DOM. */
async function drawn(lab) {
  return lab.$$eval(".plan-op", (ops) => ops.map((op) => {
    const n = (s) => Number(op.querySelector(s).textContent.replace(/,/g, ""));
    return {
      operator: op.dataset.operator,
      estimated: n(".plan-bar.estimated .plan-bar-value"),
      rows_in: n('[data-field="rows_in"]'),
      rows_out: n('[data-field="rows_out"]'),
      measured: n(".plan-bar.measured .plan-bar-value"),
    };
  }));
}

function same(label, got, want) {
  const a = JSON.stringify(got), b = JSON.stringify(want);
  if (a !== b) throw new Error(`${label}: drew ${a}, the report says ${b}`);
}

const browser = await launch();
let failures = 0;
try {
  for (const file of pages) {
    const page = await openPage(browser, directory(site));
    await page.goto(`${ORIGIN}/${file}`);
    for (const lab of await page.$$(".lab[data-experiment]")) {
      const label = `${file} ${await lab.getAttribute("data-experiment")}`;
      try {
        await page.waitForFunction((el) => el.dataset.ready === "true", lab, { timeout: 10_000 });
        const data = JSON.parse(await lab.$eval("script.lab-data", (s) => s.textContent));
        const want = expected(data.root).map((o) => ({ ...o, measured: o.rows_out }));
        same(`${label}, from the build`, await drawn(lab), want);
        await (await lab.$(".lab-foot button")).click();
        await page.waitForFunction((el) => el.dataset.source === "browser" || el.dataset.ready === "error", lab,
          { timeout: 300_000 });
        const [agrees, status] = await lab.evaluate((el) => [el.dataset.agrees, el.querySelector(".lab-status").textContent]);
        if (agrees !== "true") throw new Error(`${label}: ${status}`);
        same(`${label}, from your browser`, await drawn(lab), want);
        console.log(`  ${label}: drawn from the build, and recomputed in the browser to the same answer`);
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
if (failures) process.exit(1);
