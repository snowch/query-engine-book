// The probe under Pyodide in headless Chromium: opens page.html at a made-up origin whose
// requests are answered from the repository on disk (tests/browser/chromium.mjs), and prints what
// the page's Python printed. Pyodide and its packages come from the CDN, as they do for a reader.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ORIGIN, launch, openPage } from "../../tests/browser/chromium.mjs";
import { ROOT, RUN, probeFiles } from "./files.mjs";

const PAGE = "spikes/duckdb-pyodide/page.html";
const files = probeFiles();
const serve = (path) => {
  if (path === "files.json") return { files, run: RUN };
  return path === PAGE || files.includes(path) ? readFileSync(join(ROOT, path)) : null;
};

const browser = await launch();
try {
  const page = await openPage(browser, serve);
  await page.goto(`${ORIGIN}/${PAGE}`);
  await page.waitForSelector("#out[data-done]", { state: "attached", timeout: 240_000 });
  const [done, text] = await page.$eval("#out", (el) => [el.dataset.done, el.textContent]);
  if (done !== "ok") {
    console.error(text);
    process.exitCode = 1;
  } else {
    console.log(text);
  }
} finally {
  await browser.close();
}
