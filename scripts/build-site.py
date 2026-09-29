#!/usr/bin/env python3
"""The book as static pages, rendered from MyST's parse rather than MyST's theme.

    python3 scripts/build-site.py                 # every page, into _build/html/
    python3 scripts/build-site.py --out DIR

This is the published site, not a preview of one: the deploy runs this file against the same
parse ``make check`` does. It rests on three facts.

**MyST parses; this repository renders.** ``myst build --strict`` without ``--html`` produces the
AST and resolves every cross-reference, offline. ``tools/render.py`` walks the AST and raises on
anything it does not know. This file wraps the result in the site's chrome and writes it.

**The page is not somebody else's application.** Nothing hydrates, so the lab's script can own
the parts of the page it mounts into.

**Every URL is relative.** Pages are flat, and every asset is addressed from the page, so the
site works at a domain root, under a GitHub Pages project path, or opened from a disk.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import render as renderer  # noqa: E402
from tools.outline import APPENDICES, CHAPTERS, PARTS, UNWRITTEN  # noqa: E402

CONTENT = ROOT / "_build" / "site" / "content"
TITLE = "Queries, operator by operator"
SUBTITLE = "Build a query engine to learn what a query costs"


def page_list() -> list[dict]:
    """Every page, in reading order, with what the chrome needs to know about it."""
    # The cover is the site's front page, index.html; the preface follows it.
    pages = [
        {"source": "cover.md", "href": "index.html", "title": TITLE, "nav": "Cover", "label": None},
        {"source": "index.md", "href": "preface.html", "title": "Preface", "label": None},
    ]
    for part in PARTS:
        pages.append(
            {
                "source": part.path,
                "href": f"{part.slug.replace('_', '-')}.html",
                "title": part.title,
                "label": None,
            }
        )
        for c in CHAPTERS:
            if c.part == part.title:
                pages.append(
                    {
                        "source": c.path,
                        "href": f"{c.anchor}.html",
                        "title": c.title,
                        "label": c.label,
                        "chapter": c,
                    }
                )
    for a in APPENDICES:
        pages.append({"source": a.path, "href": f"{a.anchor}.html", "title": a.title, "label": a.label})
    return pages


def load_parse() -> dict[str, dict]:
    if not CONTENT.exists():
        sys.exit("no MyST parse at _build/site/content; run `myst build --strict` first")
    by_source = {}
    for path in CONTENT.glob("*.json"):
        data = json.loads(path.read_text())
        by_source[data["location"].lstrip("/")] = data
    return by_source


def is_unwritten(source: str) -> bool:
    return UNWRITTEN in (ROOT / source).read_text()


def nav_html(pages: list[dict], here: str) -> str:
    out = ['<nav class="nav" id="nav" aria-label="Chapters"><ol>']
    for p in pages:
        cls = ["here"] if p["href"] == here else []
        if p.get("chapter") is not None and is_unwritten(p["source"]):
            cls.append("unwritten")
        c = f' class="{" ".join(cls)}"' if cls else ""
        aria = ' aria-current="page"' if p["href"] == here else ""
        if p["source"].startswith("parts/"):
            out.append(f'<li class="part"><a href="{p["href"]}"{aria}>{html.escape(p["title"])}</a></li>')
        elif p["label"]:
            num = p["label"].replace("Appendix ", "").replace("ch", "")
            out.append(
                f'<li><a href="{p["href"]}"{c}{aria}><span class="num">{html.escape(num)}</span>'
                f"{html.escape(p['title'])}</a></li>"
            )
        else:
            out.append(f'<li><a href="{p["href"]}"{c}{aria}>{html.escape(p.get("nav", p["title"]))}</a></li>')
    out.append("</ol></nav>")
    return "".join(out)


def toc_html(mdast: dict) -> str:
    items = []
    for node in walk(mdast):
        if node.get("type") == "heading" and node.get("depth") in (2, 3):
            hid = renderer.heading_id(node)
            items.append(
                f'<li class="d{node["depth"]}"><a href="#{html.escape(hid)}">'
                f"{html.escape(renderer.text_of(node))}</a></li>"
            )
    if not items:
        return '<aside class="toc" id="toc"></aside>'
    return (
        f'<aside class="toc" id="toc" aria-label="On this page"><p>On this page</p>'
        f"<ol>{''.join(items)}</ol></aside>"
    )


def walk(node):
    if isinstance(node, dict):
        yield node
        for c in node.get("children", []):
            yield from walk(c)


def normalise_headings(mdast: dict) -> None:
    """Make the shallowest section heading an ``h2``: the page title is the only ``h1``.

    MyST drops a leading heading that repeats the frontmatter title and leaves the sections at
    depth 2. A page written without that heading would have its sections one level higher, so
    this moves them rather than trusting every author to write the same way.
    """
    depths = [n["depth"] for n in walk(mdast) if n.get("type") == "heading"]
    if not depths:
        return
    shift = 2 - min(depths)
    for n in walk(mdast):
        if n.get("type") == "heading":
            n["depth"] = max(2, min(6, n["depth"] + shift))


def commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "uncommitted"


HEAD_SCRIPT = r"""<script>
(() => {
  const root = document.documentElement;
  let theme = "system";
  try { const kept = localStorage.getItem("theme"); if (kept === "light" || kept === "dark") theme = kept; } catch (e) {}
  const apply = () => {
    if (theme === "system") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", theme);
  };
  apply();
  document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("theme");
    const names = { system: "System", light: "Light", dark: "Dark" };
    const order = ["system", "light", "dark"];
    const show = () => { button.textContent = names[theme]; button.setAttribute("aria-label", `Colours: ${names[theme]}`); };
    button.hidden = false;
    show();
    button.addEventListener("click", () => {
      theme = order[(order.indexOf(theme) + 1) % order.length];
      try { if (theme === "system") localStorage.removeItem("theme"); else localStorage.setItem("theme", theme); } catch (e) {}
      apply(); show();
    });
  });
  // Where the reader is: the page and how far down it, kept as they read. Opened from a home
  // screen, the book starts at index.html?resume (manifest.webmanifest) and goes back there; the
  // preface also offers a link back, however it was reached.
  //
  // The place is kept under a key named for this book's directory, not a bare "last-read". Books
  // served from one origin (snowch.github.io/parquet-book/, /query-engine-book/) share one
  // storage, and a bare key offered each book the other's page, which it does not have.
  const page = location.pathname.split("/").pop() || "index.html";
  const PLACE = `last-read:${location.pathname.replace(/[^/]*$/, "")}`;
  const RESUME = `resume-scroll:${location.pathname.replace(/[^/]*$/, "")}`;
  let last = null;
  try { last = JSON.parse(localStorage.getItem(PLACE)); } catch (e) {}
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const launched = new URLSearchParams(location.search).has("resume") || (standalone && !document.referrer);
  if (page === "index.html" && launched && last && last.page && last.page !== "index.html") {
    try { sessionStorage.setItem(RESUME, String(last.y || 0)); } catch (e) {}
    location.replace(last.page);
    return;
  }
  // The preface is where the book starts anyway, so it is never the place to go back to.
  const remember = () => {
    if (page === "index.html") return;
    try {
      localStorage.setItem(PLACE, JSON.stringify({ page, title: document.title.split(" · ").slice(0, -1).join(" · "), y: Math.round(scrollY) }));
    } catch (e) {}
  };
  let pending = 0;
  addEventListener("scroll", () => { clearTimeout(pending); pending = setTimeout(remember, 400); }, { passive: true });
  addEventListener("pagehide", remember);
  addEventListener("load", () => {
    let y = null;
    try { y = sessionStorage.getItem(RESUME); sessionStorage.removeItem(RESUME); } catch (e) {}
    if (y === null) return remember();
    // Labs draw after load and push the page down, so the place is kept while the page settles:
    // for a few seconds, or until the reader scrolls for themselves.
    const target = Number(y);
    const until = Date.now() + 3000;
    let moved = false;
    for (const kind of ["wheel", "touchstart", "keydown"]) addEventListener(kind, () => { moved = true; }, { once: true, passive: true });
    const hold = () => { if (!moved && Date.now() < until) scrollTo(0, target); };
    hold();
    const watch = new ResizeObserver(hold);
    watch.observe(document.body);
    setTimeout(() => watch.disconnect(), 3000);
  });
  if (page === "index.html" && last && last.page && last.page !== "index.html") {
    document.addEventListener("DOMContentLoaded", () => {
      const h1 = document.querySelector("article.page h1");
      if (!h1) return;
      const p = document.createElement("p");
      p.className = "resume";
      const a = document.createElement("a");
      a.href = last.page;
      a.textContent = `Continue reading: ${last.title || last.page}`;
      a.addEventListener("click", () => { try { sessionStorage.setItem(RESUME, String(last.y || 0)); } catch (e) {} });
      p.append(a);
      h1.after(p);
    });
  }
  if ("serviceWorker" in navigator && location.protocol !== "file:") {
    addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
  }
})();
</script>"""


#: The two rails, and whether the reader wants them. Below 58rem the chapter list is closed and
#: the Chapters button opens it over the page; where there is room it is open, and the same
#: button closes it. The outline exists only from 72rem, so its button is there and nowhere
#: else. Either choice is remembered, per browser rather than per page, and read before the page
#: paints, so a reader who closed a rail does not watch it close again on every chapter.
#:
#: The outline also hides itself when showing it would leave the chapter narrower than what it
#: holds: the prose's measure, or, on a page with code, a hundred columns of it, which is where
#: the book's code stops. A media query cannot decide that, because `rem` inside one is 16px
#: whatever the reader's text size, so it is decided here, from the rails' own computed widths
#: (neither depends on whether the outline is shown, so this cannot chase itself) and a block of
#: a hundred zeros measured in whatever monospace font this device has. Closing the chapter list
#: gives the outline its room back.
RAILS = r"""<script>
(() => {
  const root = document.documentElement;
  try {
    if (localStorage.getItem("nav") === "closed") root.classList.add("nav-closed");
    if (localStorage.getItem("toc") === "closed") root.classList.add("toc-closed");
  } catch (e) {}
  const wide = matchMedia("(min-width: 58rem)"), roomy = matchMedia("(min-width: 72rem)");
  const px = (name) => parseFloat(getComputedStyle(root).getPropertyValue(name)) || 0;
  let columns = null;
  const columnsNeed = () => {
    if (!root.classList.contains("has-code")) return 0;
    if (columns === null) {
      // Before the body exists the probe goes in the root element; the stylesheet has loaded,
      // since a script waits for the stylesheets above it, so it is styled as a block of code.
      const probe = document.createElement("pre");
      probe.textContent = "0".repeat(100);
      probe.style.cssText = "position:absolute;visibility:hidden;width:max-content;margin:0";
      (document.body || root).appendChild(probe);
      columns = probe.getBoundingClientRect().width;
      probe.remove();
    }
    return columns;
  };
  // The window less a classic scrollbar, measured rather than read from the page: before the
  // page has a body it does not scroll yet, and every page of the book does once it has.
  let bar = null;
  const room = () => {
    if (bar === null) {
      const probe = document.createElement("div");
      probe.style.cssText = "position:absolute;visibility:hidden;overflow:scroll;width:100px;height:50px";
      (document.body || root).appendChild(probe);
      bar = probe.offsetWidth - probe.clientWidth;
      probe.remove();
    }
    return innerWidth - bar;
  };
  const cramped = () => {
    if (!roomy.matches) return false;
    const rails = (root.classList.contains("nav-closed") ? 0 : px("--nav")) + px("--toc");
    return room() - rails - 2 * px("--pad") < Math.max(px("--measure"), columnsNeed());
  };
  const reflect = () => {
    root.classList.toggle("toc-cramped", cramped());
    const menu = document.getElementById("menu"), outline = document.getElementById("outline");
    if (menu) {
      const shown = wide.matches ? !root.classList.contains("nav-closed")
                                 : document.body.classList.contains("nav-open");
      menu.setAttribute("aria-expanded", String(shown));
      menu.title = `${shown ? "Hide" : "Show"} the list of chapters`;
    }
    if (outline) {
      // Where the rail cannot be laid out, neither is its button: a control for something the
      // reader cannot see is worse than none.
      outline.hidden = !roomy.matches || root.classList.contains("toc-cramped")
        || root.classList.contains("toc-none");
      const shown = !root.classList.contains("toc-closed");
      outline.setAttribute("aria-expanded", String(shown));
      outline.title = `${shown ? "Hide" : "Show"} this page's outline`;
    }
  };
  const remember = (key, closed) => {
    try { if (closed) localStorage.setItem(key, "closed"); else localStorage.removeItem(key); } catch (e) {}
  };
  reflect();
  addEventListener("resize", reflect);
  wide.addEventListener("change", () => { document.body.classList.remove("nav-open"); reflect(); });
  roomy.addEventListener("change", reflect);
  document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("menu").addEventListener("click", () => {
      if (wide.matches) remember("nav", root.classList.toggle("nav-closed"));
      else document.body.classList.toggle("nav-open");
      reflect();
    });
    document.getElementById("outline").addEventListener("click", () => {
      remember("toc", root.classList.toggle("toc-closed"));
      reflect();
    });
    columns = null;
    reflect();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { columns = null; reflect(); });
  });
})();
</script>"""


#: What the column cannot hold. A block of code or a table sits at the prose's measure, and takes
#: the wide column only when it would be cut off at the measure: the `wide` class, decided here,
#: because only the page knows the fonts it got. Each is measured once, as a copy with nothing
#: squeezing it, so a table that would wrap its cells to fit counts as cut off too, and a tab set
#: is sized by the wider of its two languages, so switching language never moves the column. A
#: table also gets `fits` and its own width, so it starts at the prose's left edge (book.css).
#:
#: Anything still cut off at the width it was given gets an Expand button, which gives it the
#: window: the same element, so an edit in progress and the reader's place both survive. On a
#: phone an expanded block reads as a page of its own, so Back closes it rather than leaving the
#: chapter: opening adds a history entry, and every way of closing goes back through it.
EXPAND = r"""<script>
document.addEventListener("DOMContentLoaded", () => {
  const root = document.documentElement;
  const article = document.querySelector("#main > .page");
  if (!article) return;
  const px = (name) => parseFloat(getComputedStyle(root).getPropertyValue(name)) || 0;
  const phone = matchMedia("(max-width: 40rem)");
  // Panels, the workbench and a run's output look after their own widths.
  const OWN = ".lab, .workbench, .run-result, .results";
  const PROMOTE = "pre, .runnable, .wide-block, .table-wrap, .generated, .tab-set, figure.quoted";

  let scrolled = 0;
  const label = (button, open) => {
    button.querySelector("span").textContent = open ? "Close" : "Expand";
    button.setAttribute("aria-expanded", String(open));
  };
  const shut = () => {
    const box = article.querySelector(".expanded");
    if (!box) return;
    box.classList.remove("expanded");
    root.classList.remove("expand-open");
    const button = box.querySelector(".expand");
    label(button, false);
    // It left the flow while it was open, so the page under it moved. Put the reader back where
    // they were rather than wherever the shorter page ended up.
    scrollTo({ top: scrolled, behavior: "instant" });
    button.focus({ preventScroll: true });
    schedule();
  };
  const close = () => {
    if (!article.querySelector(".expanded")) return;
    if (history.state && history.state.expanded) history.back();
    else shut();
  };
  addEventListener("popstate", shut);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") close(); });

  const control = (box) => {
    const button = document.createElement("button");
    button.className = "expand";
    button.type = "button";
    button.hidden = true;
    button.setAttribute("aria-expanded", "false");
    button.title = "Show all of it, in the whole window";
    button.innerHTML = '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">'
      + '<path d="M6 2H2v4M10 14h4v-4M2 10v4h4M14 6V2h-4" fill="none" stroke="currentColor"'
      + ' stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Expand</span>';
    button.addEventListener("click", () => {
      if (box.classList.contains("expanded")) { close(); return; }
      scrolled = scrollY;
      history.pushState({ expanded: true }, "");
      box.classList.add("expanded");
      root.classList.add("expand-open");
      label(button, true);
    });
    return button;
  };
  // The box a block opens in: a quoted file is its own, with the button in its bar; anything
  // else is wrapped, with a command's Run button and its output inside the wrapper.
  const boxOf = (el) => {
    const quoted = el.closest("figure.quoted");
    if (quoted) {
      if (!quoted.querySelector(":scope > .source-bar > .expand")) {
        quoted.querySelector(":scope > .source-bar").append(control(quoted));
      }
      return quoted;
    }
    const wrapped = el.closest(".wide-block");
    if (wrapped) return wrapped;
    const target = el.parentElement.classList.contains("runnable") ? el.parentElement : el;
    const box = document.createElement("div");
    box.className = "wide-block";
    target.before(box);
    box.append(control(box), target);
    while (box.nextElementSibling && box.nextElementSibling.matches(".run-result, .run-note")) {
      box.append(box.nextElementSibling);
    }
    return box;
  };

  // What each block needs with nothing squeezing it: a copy, laid out out of sight at its
  // content's width. A block of code never changes, so its answer is kept; an edited step's
  // text area is measured each time, as a block of its text in its own font.
  const kept = new WeakMap();
  const needs = (els) => {
    const meter = document.createElement("div");
    meter.style.cssText = "position:fixed;left:0;top:0;visibility:hidden;pointer-events:none;"
      + "width:max-content;height:0;overflow:hidden";
    const copies = els.map((el) => {
      if (kept.has(el)) return null;
      let copy;
      if (el.matches("textarea")) {
        const cs = getComputedStyle(el);
        copy = document.createElement("pre");
        copy.textContent = el.value;
        copy.style.cssText = `font:${cs.font};padding:0 ${cs.paddingRight} 0 ${cs.paddingLeft};`
          + `border:0 solid;border-width:0 ${cs.borderRightWidth} 0 ${cs.borderLeftWidth};`
          + `tab-size:${cs.tabSize}`;
      } else if (el.matches(".table-wrap")) {
        const table = el.querySelector("table");
        // On a phone a table of many columns is a card per row, which is never cut off.
        if (!table || (table.matches(".cards") && phone.matches)) return null;
        copy = table.cloneNode(true);
        copy.style.display = "table";
      } else {
        copy = el.cloneNode(true);
      }
      copy.style.width = "max-content";
      copy.style.maxWidth = "none";
      copy.style.margin = "0";
      copy.style.overflow = "visible";
      meter.append(copy);
      return copy;
    });
    document.body.append(meter);
    const out = els.map((el, i) => {
      if (!copies[i]) return kept.get(el) || 0;
      const width = copies[i].getBoundingClientRect().width;
      if (!el.matches("textarea")) kept.set(el, width);
      return width;
    });
    meter.remove();
    return out;
  };
  const topOf = (el) => {
    while (el && el.parentElement !== article) el = el.parentElement;
    return el;
  };

  let width = -1;
  const layout = () => {
    pending = false;
    if (root.classList.contains("expand-open")) return;
    const blocks = [...article.querySelectorAll("pre, textarea.code-area, .table-wrap")]
      .filter((el) => !el.closest(OWN) && !el.matches(".table-wrap pre"));
    const boxes = blocks.map(boxOf);
    const need = needs(blocks);
    const prose = Math.min(article.clientWidth, px("--measure"));
    width = article.clientWidth;
    // Each top-level block takes the wide column if anything in it would be cut off at the
    // measure. A block inside a list or a note keeps its place, and gets the button if it needs it.
    const units = new Map();
    blocks.forEach((el, i) => {
      const unit = topOf(el);
      if (!unit || !unit.matches(PROMOTE)) return;
      const u = units.get(unit) || { need: 0, tables: true };
      u.need = Math.max(u.need, need[i]);
      u.tables = u.tables && el.matches(".table-wrap");
      units.set(unit, u);
    });
    for (const el of article.querySelectorAll(":scope > .wide")) {
      if (!units.has(el)) el.classList.remove("wide", "fits");
    }
    for (const [unit, u] of units) {
      const wide = u.need > prose + 1;
      unit.classList.toggle("wide", wide);
      unit.classList.toggle("fits", wide && u.tables);
      if (wide && u.tables) unit.style.setProperty("--need", `${Math.ceil(u.need)}px`);
    }
    // Then, at the width each was given, which are still cut off. A block in the other language's
    // tab is not laid out; it is asked again when the reader switches.
    const cut = blocks.map((el, i) => el.offsetParent !== null
      && need[i] > (el.matches(".table-wrap") ? el.clientWidth : el.offsetWidth) + 1);
    blocks.forEach((el, i) => {
      if (el.offsetParent === null) return;
      const button = boxes[i].querySelector(":scope > .expand, :scope > .source-bar > .expand");
      button.hidden = !cut[i];
    });
  };
  let pending = false;
  const schedule = () => {
    if (!pending) { pending = true; requestAnimationFrame(layout); }
  };
  layout();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(schedule);
  // The column changes width with the window and when a rail opens or closes.
  new ResizeObserver(() => { if (article.clientWidth !== width) schedule(); }).observe(article);
  document.addEventListener("click", (event) => { if (event.target.closest(".tab-bar")) schedule(); });
  // A walkthrough step swaps its code for a text area and back, and the reader types into it.
  new MutationObserver((records) => {
    if (records.some((r) => [...r.addedNodes].some((n) => n.nodeName === "PRE" || n.nodeName === "TEXTAREA"))) {
      schedule();
    }
  }).observe(article, { childList: true, subtree: true });
  article.addEventListener("input", (event) => { if (event.target.matches("textarea.code-area")) schedule(); });
});
</script>"""


def page_html(
    p: dict, body: str, nav: str, toc: str, prev: dict | None, nxt: dict | None, stamp: str, has_lab: bool
) -> str:
    chapter = p.get("chapter")
    if p["label"]:
        h1 = f'<h1><span class="label">{html.escape(p["label"])}</span>{html.escape(p["title"])}</h1>'
    else:
        h1 = f"<h1>{html.escape(p['title'])}</h1>"
    builds = ""
    if chapter is not None:
        # A chapter that explains and builds nothing says what it shows instead.
        what = "What you see" if chapter.explainer else "What you build"
        builds = f'<p class="builds"><strong>{what}:</strong> {html.escape(chapter.builds)}</p>'

    def link(q, cls, word):
        if q is None:
            return ""
        label = f"{q['label']} · " if q["label"] else ""
        return (
            f'<a class="{cls}" href="{q["href"]}"><small>{word}</small>{html.escape(label + q["title"])}</a>'
        )

    lab = (
        '<link rel="stylesheet" href="lab/lab.css"><script type="module" src="lab/lab.js"></script>'
        if has_lab
        else ""
    )
    title = f"{p['label']} · {p['title']}" if p["label"] else p["title"]
    # What the rails' script needs to know before the page has a body: whether this page has
    # sections for an outline to list, and whether it shows code, which asks more of the column.
    classes = [c for c, on in (("toc-none", "<ol>" not in toc), ("has-code", "<pre" in body)) if on]
    attrs = f' class="{" ".join(classes)}"' if classes else ""
    return f"""<!doctype html>
<html lang="en-GB"{attrs}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · {TITLE}</title>
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon-maskable-192.png">
<meta name="theme-color" content="{ICON_BACKGROUND}">
<link rel="stylesheet" href="book.css">
{lab}
{HEAD_SCRIPT}
{RAILS}
{EXPAND}
</head>
<body>
<header class="top">
<button id="menu" type="button" aria-controls="nav" aria-expanded="false">Chapters</button>
<a class="brand" href="index.html">{TITLE} <span>· {SUBTITLE}</span></a>
<button id="outline" type="button" aria-controls="toc" aria-expanded="true" hidden>On this page</button>
<button id="theme" type="button" hidden>System</button>
</header>
<div class="layout">
{nav}
<main id="main"><article class="page">
{h1}
{builds}
{body}
<nav class="prevnext" aria-label="Previous and next">{link(prev, "prev", "Previous")}{link(nxt, "next", "Next")}</nav>
<p class="stamp">{html.escape(stamp)}</p>
</article></main>
{toc}
</div>
</body>
</html>
"""


#: The book's icon, in a 32-unit square: three bars stacked like a plan's operators, narrowing
#: upwards as rows are thrown away on the way up, the top one amber like the reader's prediction in
#: the panels. Dark slate, not the Parquet book's blue columns, so the two books are told apart on a
#: home screen. (x, y, width, height, corner radius, colour). The SVG and every PNG draw these.
ICON_BACKGROUND = "#263238"
ICON_BARS = (
    (5, 20, 22, 5, 1.5, "#ffffff"),
    (8.5, 13.5, 15, 5, 1.5, "#c9d5db"),
    (12, 7, 8, 5, 1.5, "#e0a34e"),
)
#: A maskable icon fills its square, and the platform cuts it to a circle or a rounded shape. Only
#: the centre circle, of radius 40% of the square, is sure to show, so the bars are drawn smaller,
#: about the centre, until every corner falls inside it (tests/test_site.py checks).
MASKABLE_SCALE = 0.85

#: Every icon the site writes: file name, size in pixels, and whether it is maskable.
ICONS = (
    ("icon-192.png", 192, False),
    ("icon-512.png", 512, False),
    ("icon-maskable-192.png", 192, True),
    ("icon-maskable-512.png", 512, True),
)


def _icon_shapes(maskable: bool):
    """The bars, scaled about the centre for a maskable icon."""
    k = MASKABLE_SCALE if maskable else 1.0
    for x, y, w, h, r, colour in ICON_BARS:
        yield 16 + (x - 16) * k, 16 + (y - 16) * k, w * k, h * k, r * k, colour


def favicon_svg() -> str:
    bars = "".join(
        f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{r:g}" fill="{c}"/>\n'
        for x, y, w, h, r, c in _icon_shapes(False)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">\n'
        f'<rect width="32" height="32" rx="6" fill="{ICON_BACKGROUND}"/>\n{bars}</svg>\n'
    )


def icon_png(size: int, maskable: bool = False) -> bytes:
    """The icon as a PNG ``size`` pixels square: home screens want a bitmap. Drawn here, from the
    same shapes as the SVG, so the build needs no image library and writes the same bytes every
    time. A maskable icon's background fills the whole square; the ordinary one has rounded
    corners, transparent outside them."""
    import struct
    import zlib

    def rgb(colour: str) -> tuple[int, int, int]:
        return int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)

    background = rgb(ICON_BACKGROUND)
    bars = [(x, y, w, h, r, rgb(c)) for x, y, w, h, r, c in _icon_shapes(maskable)]

    def inside(x: float, y: float, rx: float, ry: float, w: float, h: float, r: float) -> bool:
        cx = min(max(x, rx + r), rx + w - r)
        cy = min(max(y, ry + r), ry + h - r)
        return rx <= x <= rx + w and ry <= y <= ry + h and (x - cx) ** 2 + (y - cy) ** 2 <= r * r

    samples = ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))
    raw = bytearray()
    for py in range(size):
        raw.append(0)  # no filter on this scanline
        for px in range(size):
            total, alpha = [0.0, 0.0, 0.0], 0.0
            for sx, sy in samples:
                x, y = (px + sx) * 32 / size, (py + sy) * 32 / size
                if not maskable and not inside(x, y, 0, 0, 32, 32, 6):
                    continue
                colour = next(
                    (c for bx, by, bw, bh, br, c in bars if inside(x, y, bx, by, bw, bh, br)), background
                )
                for i in range(3):
                    total[i] += colour[i]
                alpha += 1
            colour = [round(c / alpha) if alpha else 0 for c in total]
            raw += bytes([*colour, round(255 * alpha / len(samples))])

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def manifest() -> str:
    """The book as an app on a home screen. It starts at ``index.html?resume``, which the page's
    script turns into the page the reader was last on (HEAD_SCRIPT)."""
    return json.dumps(
        {
            "name": TITLE,
            "short_name": "Queries",
            "start_url": "index.html?resume",
            "scope": "./",
            "display": "standalone",
            "background_color": "#fdfdfc",
            "theme_color": ICON_BACKGROUND,
            # Android draws a maskable icon edge to edge in its own shape; anywhere else, the
            # ordinary icon, with its own rounded corners.
            "icons": [
                *(
                    {
                        "src": name,
                        "sizes": f"{size}x{size}",
                        "type": "image/png",
                        "purpose": "maskable" if maskable else "any",
                    }
                    for name, size, maskable in ICONS
                ),
                {"src": "favicon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
            ],
        },
        indent=2,
    )


def service_worker(files: list[str], version: str) -> str:
    """Keep every file of the site on first visit, so the book reads with no network after it.

    The list is every file the build wrote, and the cache name carries a hash of their contents,
    so a new deploy replaces the old copy instead of mixing with it.
    """
    return f"""// Written by scripts/build-site.py. Keeps the whole book for offline reading.
const CACHE = "query-engine-book-{version}";
const FILES = {json.dumps(files)};
self.addEventListener("install", (e) => {{
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(FILES)).then(() => self.skipWaiting()));
}});
self.addEventListener("activate", (e) => {{
  e.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
}});
self.addEventListener("fetch", (e) => {{
  // Only the book's own files: Pyodide, fetched from a CDN for the Python the page runs, is
  // cached by the browser as any other download.
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(caches.match(e.request, {{ ignoreSearch: true }}).then((hit) => hit || fetch(e.request)));
}});
"""


def build(out: Path) -> None:
    parse = load_parse()
    pages = page_list()
    missing = [p["source"] for p in pages if p["source"] not in parse]
    if missing:
        sys.exit(f"MyST produced no parse for: {', '.join(missing)}. Is each page in myst.yml's toc?")
    renderer.PAGES.clear()
    renderer.IMAGES.clear()
    for p in pages:
        renderer.PAGES[parse[p["source"]]["slug"]] = p["href"]

    if out.exists():
        shutil.rmtree(out)
    (out / "lab").mkdir(parents=True)
    (out / "fixtures").mkdir()

    stamp = f"Built from commit {commit()}."
    for i, p in enumerate(pages):
        mdast = parse[p["source"]]["mdast"]
        normalise_headings(mdast)
        body = renderer.render_page(mdast)
        # Only a page that mounts a panel or a workbench loads the lab's script.
        markers = ('class="lab"', 'class="workbench"')
        has_lab = any(m in body for m in markers)
        text = page_html(
            p,
            body,
            nav_html(pages, p["href"]),
            toc_html(mdast),
            pages[i - 1] if i > 0 else None,
            pages[i + 1] if i + 1 < len(pages) else None,
            stamp,
            has_lab,
        )
        (out / p["href"]).write_text(text)

    shutil.copy(ROOT / "web" / "book.css", out / "book.css")
    for image in sorted(renderer.IMAGES):
        (out / image).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / image, out / image)
    (out / "favicon.svg").write_text(favicon_svg())
    for name, size, maskable in ICONS:
        (out / name).write_bytes(icon_png(size, maskable))
    (out / "manifest.webmanifest").write_text(manifest())
    lab = ROOT / "web" / "lab"
    if lab.is_dir():
        for f in lab.iterdir():
            if f.suffix in (".js", ".css"):
                shutil.copy(f, out / "lab" / f.name)
    # The Python the page runs under Pyodide: the book's engine, and the Parquet book's reader,
    # which is its scan layer, from the pinned submodule. The same files the tests import.
    packages = {
        "query_lab": ROOT / "python" / "query_lab",
        "parquet_lab": ROOT / "external" / "parquet-book" / "python" / "parquet_lab",
    }
    listing: dict[str, list[str]] = {}
    for name, package in packages.items():
        if not package.is_dir():
            sys.exit(f"{package.relative_to(ROOT)} is missing; run `git submodule update --init`")
        (out / "lab" / "py" / name).mkdir(parents=True)
        listing[name] = sorted(f.name for f in package.glob("*.py"))
        for module in listing[name]:
            shutil.copy(package / module, out / "lab" / "py" / name / module)
    # Every fixture, with its manifest, and every table of many files, as a directory.
    for f in sorted((ROOT / "fixtures").glob("*")):
        if f.suffix in (".parquet", ".json"):
            shutil.copy(f, out / "fixtures" / f.name)
        elif f.is_dir() and (f / "metadata.json").is_file():
            shutil.copytree(f, out / "fixtures" / f.name, ignore=shutil.ignore_patterns("__pycache__"))
    fixtures = sorted(
        str(f.relative_to(out / "fixtures")) for f in (out / "fixtures").rglob("*") if f.is_file()
    )
    # The queries the panels run, as the repository keeps them.
    queries = sorted(f.name for f in (ROOT / "queries").glob("*.sql"))
    (out / "lab" / "py" / "queries").mkdir()
    for name in queries:
        shutil.copy(ROOT / "queries" / name, out / "lab" / "py" / "queries" / name)
    # The problems, their graders and the conftest that gates them, for the workbench.
    exercises = sorted(
        str(f.relative_to(ROOT / "exercises"))
        for f in (ROOT / "exercises").rglob("*.py")
        if "__pycache__" not in f.parts
    )
    for name in exercises:
        (out / "lab" / "py" / "exercises" / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / "exercises" / name, out / "lab" / "py" / "exercises" / name)
    # The engine's tests, which a chapter may run on the reader's edit of a listing.
    tests = sorted(f.name for f in (ROOT / "python" / "tests").glob("*.py"))
    (out / "lab" / "py" / "tests").mkdir()
    for name in tests:
        shutil.copy(ROOT / "python" / "tests" / name, out / "lab" / "py" / "tests" / name)
    (out / "lab" / "py" / "package.json").write_text(
        json.dumps(
            {
                "packages": listing,
                "queries": queries,
                "exercises": exercises,
                "tests": tests,
                "fixtures": fixtures,
            }
        )
    )
    (out / ".nojekyll").write_text("")

    files = sorted(str(f.relative_to(out)) for f in out.rglob("*") if f.is_file() and f.name != ".nojekyll")
    digest = hashlib.sha256()
    for f in files:
        digest.update(f.encode())
        digest.update((out / f).read_bytes())
    (out / "sw.js").write_text(service_worker(["./", *files], digest.hexdigest()[:12]))
    where = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"wrote {len(pages)} pages and {len(files) - len(pages)} assets to {where}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "_build" / "html"))
    args = parser.parse_args()
    build(Path(args.out).resolve())


if __name__ == "__main__":
    main()
