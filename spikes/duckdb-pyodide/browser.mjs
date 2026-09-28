// The probe under Pyodide in headless Chromium: opens page.html at a made-up origin whose
// requests Playwright answers from the repository on disk, and prints what the page's Python
// printed. Pyodide and its packages come from the CDN, as they do for a reader. Needs Playwright
// and a Chromium.

import { X509Certificate, createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ROOT, RUN, probeFiles } from "./files.mjs";

let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  const { createRequire } = await import("node:module");
  const { execSync } = await import("node:child_process");
  const global = execSync("npm root -g").toString().trim();
  ({ chromium } = createRequire(join(global, "noop.js"))("playwright"));
}

// Answered by page.route below, never by a network: no server to start, and nothing for a
// proxy to intercept.
const ORIGIN = "http://book.invalid";
const PAGE = "spikes/duckdb-pyodide/page.html";
const TYPES = { ".html": "text/html", ".py": "text/plain", ".sql": "text/plain", ".parquet": "application/octet-stream" };
const files = probeFiles();

// Behind an HTTPS proxy (some sandboxes), the page reaches the CDN through it. A proxy that
// re-signs traffic with its own certificate authority names that authority's certificate in
// BROWSER_EXTRA_CA; Chromium is told to trust that one key, and still checks every certificate.
const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;
const args = [];
if (process.env.BROWSER_EXTRA_CA) {
  const ca = new X509Certificate(readFileSync(process.env.BROWSER_EXTRA_CA));
  const spki = ca.publicKey.export({ type: "spki", format: "der" });
  args.push(`--ignore-certificate-errors-spki-list=${createHash("sha256").update(spki).digest("base64")}`);
}
const browser = await chromium.launch({ args, ...(proxy ? { proxy: { server: proxy } } : {}) });
try {
  const page = await browser.newPage();
  // What the page and its downloads did, on stderr, so a failure says where it stopped.
  page.on("console", (m) => console.error(`page: ${m.text()}`));
  page.on("pageerror", (e) => console.error(`page error: ${e.message}`));
  page.on("requestfailed", (r) => console.error(`request failed: ${r.url()} ${r.failure()?.errorText}`));
  await page.route(`${ORIGIN}/**`, (route) => {
    const path = decodeURIComponent(new URL(route.request().url()).pathname).slice(1);
    if (path === "files.json") return route.fulfill({ json: { files, run: RUN } });
    const name = path === "" ? PAGE : path;
    if (name !== PAGE && !files.includes(name)) return route.fulfill({ status: 404 });
    return route.fulfill({
      body: readFileSync(join(ROOT, name)),
      contentType: TYPES[name.slice(name.lastIndexOf("."))] || "application/octet-stream",
    });
  });
  await page.goto(`${ORIGIN}/`);
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
