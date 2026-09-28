// Headless Chromium for the browser checks, serving files from disk at a made-up origin.
//
// Requests to ORIGIN are answered by the context's route handler from a directory on disk: no
// server to start, and nothing for a proxy to intercept (Playwright sends even loopback traffic
// through a configured proxy). The context's handler also answers the page's workers. Everything
// else, Pyodide and its packages from the CDN, goes to the network, as it does for a reader.

import { X509Certificate, createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join, normalize } from "node:path";

export const ORIGIN = "http://book.invalid";

const TYPES = {
  ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".py": "text/plain", ".sql": "text/plain", ".svg": "image/svg+xml",
  ".png": "image/png", ".parquet": "application/octet-stream",
};

async function playwright() {
  try {
    return await import("playwright");
  } catch {
    const { createRequire } = await import("node:module");
    const { execSync } = await import("node:child_process");
    const global = execSync("npm root -g").toString().trim();
    return createRequire(join(global, "noop.js"))("playwright");
  }
}

/**
 * A browser behind whatever HTTPS proxy the environment names. A proxy that re-signs traffic with
 * its own certificate authority names that authority's certificate in BROWSER_EXTRA_CA; Chromium
 * is told to trust that one key, and still checks every certificate.
 */
export async function launch() {
  const { chromium } = await playwright();
  const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;
  const args = [];
  if (process.env.BROWSER_EXTRA_CA) {
    const ca = new X509Certificate(readFileSync(process.env.BROWSER_EXTRA_CA));
    const spki = ca.publicKey.export({ type: "spki", format: "der" });
    args.push(`--ignore-certificate-errors-spki-list=${createHash("sha256").update(spki).digest("base64")}`);
  }
  return chromium.launch({ args, ...(proxy ? { proxy: { server: proxy } } : {}) });
}

/**
 * A page whose requests to ORIGIN are answered by `serve(path)`, which returns a file's bytes or
 * null. What the page and its downloads did goes to stderr, so a failure says where it stopped.
 * `options` go to the browser context: `{ javaScriptEnabled: false }`, say.
 */
export async function openPage(browser, serve, options = {}) {
  const context = await browser.newContext(options);
  await context.route(`${ORIGIN}/**`, (route) => {
    const path = decodeURIComponent(new URL(route.request().url()).pathname).slice(1);
    const body = serve(path);
    if (body === null) return route.fulfill({ status: 404 });
    if (typeof body === "object" && !(body instanceof Uint8Array) && !Buffer.isBuffer(body)) {
      return route.fulfill({ json: body });
    }
    return route.fulfill({ body, contentType: TYPES[path.slice(path.lastIndexOf("."))] || "application/octet-stream" });
  });
  const page = await context.newPage();
  page.on("console", (m) => console.error(`page: ${m.text()}`));
  page.on("pageerror", (e) => console.error(`page error: ${e.message}`));
  page.on("requestfailed", (r) => console.error(`request failed: ${r.url()} ${r.failure()?.errorText}`));
  return page;
}

/** A `serve` for a directory: its files, and nothing outside it. */
export function directory(root) {
  return (path) => {
    const file = normalize(join(root, path || "index.html"));
    if (!file.startsWith(root) || !existsSync(file)) return null;
    return readFileSync(file);
  };
}
