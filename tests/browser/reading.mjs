// The untouched reading route: no Python runtime, no JavaScript, and native disclosures.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { resolve, join } from "node:path";
import { ORIGIN, directory, launch, openPage } from "./chromium.mjs";

const site = resolve(process.argv[2] || "_build/html");
const pages = readdirSync(site).filter((f) => f.endsWith(".html")
  && readFileSync(join(site, f), "utf8").includes('class="reading-guide"'));
assert.equal(pages.length, 19);
const browser = await launch();
try {
  for (const javaScriptEnabled of [false, true]) {
    const page = await openPage(browser, directory(site), { reading: true, javaScriptEnabled });
    const downloads = [];
    page.on("request", (request) => {
      if (/pyodide|\.whl(?:\?|$)/.test(request.url())) downloads.push(request.url());
    });
    for (const file of pages) {
      await page.goto(`${ORIGIN}/${file}`);
      assert.equal(await page.locator("details.optional[open]").count(), 0, `${file}: optional tools start closed`);
      assert.equal(await page.locator(".checkpoint").count(), 1);
      assert.equal(await page.locator(".reading-guide").count(), 1);
      const result = page.locator(".worked-result").first();
      assert(await result.isVisible(), `${file}: results visible without running`);
      assert.equal(await page.locator(".worked-result .table-wrap").count() > 0, true);
      const code = page.locator(".code-disclosure").first();
      assert(await code.count());
      assert(!(await code.locator("figure").isVisible()));
      await code.locator(":scope > summary").focus();
      await page.keyboard.press("Enter");
      assert(await code.locator("figure").isVisible(), `${file}: keyboard opens code`);
      await code.locator(":scope > summary").press("Enter");
      const answer = page.locator(".checkpoint details");
      assert(!(await answer.locator("p").isVisible()));
      await answer.locator("summary").focus();
      await page.keyboard.press("Enter");
      assert(await answer.locator("p").isVisible(), `${file}: explanation opens without scripts`);
      for (const width of [390, 1440]) {
        await page.setViewportSize({ width, height: 900 });
        for (const colorScheme of ["light", "dark"]) {
          await page.emulateMedia({ colorScheme });
          const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
          assert(overflow <= 1, `${file}: horizontal page overflow ${overflow} at ${width}/${colorScheme}`);
        }
      }
      // A code sample's runtime metadata remains inside its disclosure and next to the figure.
      assert.equal(await page.locator("script.run-then").evaluateAll((nodes) => nodes.every((s) =>
        s.previousElementSibling.matches("figure.quoted") && s.parentElement.matches("details.code-disclosure"))), true);
    }
    assert.equal(downloads.length, 0, "reading must not download the Python runtime");
    await page.context().close();
    console.log(`PASS ${pages.length} reading routes, JavaScript ${javaScriptEnabled ? "on" : "off"}`);
  }
} finally {
  await browser.close();
}
