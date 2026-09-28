// The site's own chrome, driven in headless Chromium, served as GitHub Pages serves it: under
// /query-engine-book/ on an origin other books share.
//
//   node tests/browser/site.mjs _build/html
//
// 1. Another book's saved place is not offered. The Parquet book, on the same origin, keeps its
//    reader's place in the same browser storage; this book must neither read it nor write where
//    that book reads.
// 2. This book's own place is offered on the cover, and links to a page it has.
// 3. The cover's picture sits in the text column, aligned with the paragraphs.

import { existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { ORIGIN, directory, launch, openPage } from "./chromium.mjs";

const site = resolve(process.argv[2] || "_build/html");
const BASE = "query-engine-book/";
const files = directory(site);
const serve = (path) => (path.startsWith(BASE) ? files(path.slice(BASE.length)) : null);

function check(ok, message) {
  if (!ok) throw new Error(message);
}

const browser = await launch();
try {
  const page = await openPage(browser, serve);
  // What the Parquet book leaves behind, before this book's first page loads.
  await page.addInitScript(() => {
    if (!sessionStorage.getItem("planted")) {
      localStorage.setItem("last-read", JSON.stringify({ page: "why-parquet-exists.html", title: "ch01 · Why Parquet exists", y: 0 }));
      sessionStorage.setItem("planted", "yes");
    }
  });
  await page.setViewportSize({ width: 1300, height: 900 });
  await page.goto(`${ORIGIN}/${BASE}`);
  check(!(await page.$("p.resume")), "the cover offers another book's saved place");
  console.log("  another book's saved place is not offered");

  await page.goto(`${ORIGIN}/${BASE}the-plan-is-the-map.html`);
  await page.evaluate(() => scrollTo(0, 400));
  await page.waitForTimeout(600);
  await page.goto(`${ORIGIN}/${BASE}`);
  const resume = await page.$eval("p.resume a", (a) => [a.getAttribute("href"), a.textContent]).catch(() => null);
  check(resume, "the cover does not offer the page just read");
  check(resume[1].includes("The plan is the map") && existsSync(join(site, resume[0])), `the cover offers ${resume}`);
  const foreign = await page.evaluate(() => JSON.parse(localStorage.getItem("last-read")).page);
  check(foreign === "why-parquet-exists.html", "this book overwrote the Parquet book's saved place");
  console.log("  this book's own place is offered, and the other book's is left alone");

  const [img, text] = await page.evaluate(() => {
    const box = (e) => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right)]; };
    return [box(document.querySelector("article img")), box(document.querySelector("article > p:not(.resume):not(.builds)"))];
  });
  check(Math.abs(img[0] - text[0]) <= 1 && img[1] <= text[1] + 1, `the cover's picture spans ${img}, the text ${text}`);
  console.log("  the cover's picture sits in the text column");
} finally {
  await browser.close();
}
