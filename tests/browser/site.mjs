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
// 4. On a phone, the list of chapters opens below the bar, starting at the cover, and scrolls
//    within the screen when it is taller than the screen.

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

  for (const height of [900, 480]) {
    await page.setViewportSize({ width: 390, height });
    await page.goto(`${ORIGIN}/${BASE}joins.html`);
    await page.click("#menu");
    const drawer = await page.evaluate(() => {
      const nav = document.querySelector("#nav").getBoundingClientRect();
      const bar = document.querySelector(".top").getBoundingClientRect();
      const first = document.querySelector("#nav li a");
      const list = document.querySelector("#nav");
      return { top: nav.top, bottom: nav.bottom, bar: bar.bottom, first: first.getBoundingClientRect().top,
               text: first.textContent, scrolls: list.scrollHeight > list.clientHeight, innerHeight };
    });
    check(Math.abs(drawer.top - drawer.bar) <= 1 && drawer.first >= drawer.bar, `the chapter list opens under the bar: ${JSON.stringify(drawer)}`);
    check(drawer.text === "Cover" && drawer.bottom <= drawer.innerHeight + 1, `the chapter list fits the screen from the cover: ${JSON.stringify(drawer)}`);
    check(height > 600 || drawer.scrolls, "a short screen's chapter list scrolls");
  }
  console.log("  on a phone, the chapter list opens under the bar, starts at the cover, and scrolls");
} finally {
  await browser.close();
}
