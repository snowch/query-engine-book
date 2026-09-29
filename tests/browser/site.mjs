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
// 5. On a phone, a plan wider than its panel, as a join's is, scrolls to both of its ends.
// 6. On a phone, Back closes the open list of chapters and stays on the page, and the list leaves
//    nothing behind in the history, however it was closed.

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

  for (const [height, chapter] of [[900, "joins.html"], [480, "sorting-and-top-k.html"]]) {
    await page.setViewportSize({ width: 390, height });
    await page.goto(`${ORIGIN}/${BASE}${chapter}`);
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

  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto(`${ORIGIN}/${BASE}the-plan-is-the-map.html`);
  const ends = await page.evaluate(async () => {
    const { EXPERIMENTS } = await import("./lab/panels.js");
    const data = JSON.parse(document.querySelector("script.lab-data").textContent);
    // The chapter's plan, with a second input beside the scan: two operators side by side.
    const below = data.root.children[0];
    below.children = [structuredClone(below.children[0]), structuredClone(below.children[0])];
    const host = document.createElement("div");
    host.className = "lab";
    document.querySelector("#main").prepend(host);
    EXPERIMENTS.plan(host, data, { store: { get: () => null, set() {}, drop() {} }, key: "wide" });
    const tree = host.querySelector(".plan-tree");
    const ops = [...host.querySelectorAll(".plan-op")];
    const edge = () => tree.getBoundingClientRect();
    tree.scrollLeft = 0;
    const left = Math.min(...ops.map((o) => o.getBoundingClientRect().left)) >= edge().left;
    tree.scrollLeft = tree.scrollWidth;
    const right = Math.max(...ops.map((o) => o.getBoundingClientRect().right)) <= edge().right + 1;
    return { left, right, wider: tree.scrollWidth > tree.clientWidth };
  });
  check(ends.wider && ends.left && ends.right, `a wide plan cannot be scrolled to both ends: ${JSON.stringify(ends)}`);
  console.log("  on a phone, a plan wider than its panel scrolls to both of its ends");

  const open = () => page.evaluate(() => document.body.classList.contains("nav-open"));
  const at = () => new URL(page.url()).pathname.split("/").pop();
  const back = async () => { await page.goBack(); await page.waitForTimeout(150); };
  await page.setViewportSize({ width: 390, height: 800 });
  // Back closes the list, and a second Back leaves the page.
  await page.goto(`${ORIGIN}/${BASE}skew.html`);
  await page.goto(`${ORIGIN}/${BASE}joins.html`);
  await page.click("#menu");
  check(await open(), "the menu did not open the chapter list");
  await back();
  check(!(await open()) && at() === "joins.html", `Back did not close the list in place: ${at()}`);
  await back();
  check(at() === "skew.html", `the list left an entry in the history: Back went to ${at()}`);
  // Closed with its own button, the list leaves nothing behind either.
  await page.goto(`${ORIGIN}/${BASE}joins.html`);
  await page.click("#menu");
  await page.click("#menu");
  await page.waitForTimeout(150);
  check(!(await open()), "the menu did not close the chapter list");
  await back();
  check(at() === "skew.html", `closing the list left an entry in the history: Back went to ${at()}`);
  // A chapter chosen from the list: Back returns to the page, with the list closed.
  await page.goto(`${ORIGIN}/${BASE}joins.html`);
  await page.click("#menu");
  await Promise.all([page.waitForURL(/hash-aggregation\.html/), page.click('#nav a[href="hash-aggregation.html"]')]);
  check(!(await open()), "the chosen chapter opened with the list open");
  await back();
  check(at() === "joins.html" && !(await open()), `Back from the chosen chapter: ${at()}, list open ${await open()}`);
  await back();
  check(at() === "skew.html", `choosing a chapter left an entry in the history: Back went to ${at()}`);
  console.log("  on a phone, Back closes the chapter list, and the list leaves nothing in the history");
} finally {
  await browser.close();
}
