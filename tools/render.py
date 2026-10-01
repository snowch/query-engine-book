"""MyST's parse, rendered to HTML: the one renderer every page of the book goes through.

The input is MyST's own parse output, the JSON ``myst build`` writes under
``_build/site/content/``, not the markdown. Directives are already resolved in it: every
``{literalinclude}`` carries the real code from the working tree and every ``{include}`` carries
the real generated fragment, so there is no second implementation of either to drift.

A node type the renderer does not know **raises**. It is never skipped: a renderer that quietly
drops what it does not recognise loses content, and the only symptom is a paragraph nobody
notices is missing.

Three node shapes are this book's own:

- A fenced block in the language ``lab`` is an experiment: a panel. It becomes a mount point
  that ``web/lab/lab.js`` draws, carrying the panel's JSON as the build computed it
  (``python -m query_lab figures``), so it draws with nothing to download. Without JavaScript it
  says it needs JavaScript. The renderer checks that the experiment, the query and the fixtures
  it names exist, and that the JSON is there.
- A fenced block in the language ``timed`` names a timing in ``query_lab.timing``: cases the
  page times in the reader's browser when asked, and shows with how long each took there. The
  page carries the cases, never a time: the build's machine is not the reader's. The renderer
  checks the timing exists and its cases were generated.
- A fenced block in the language ``problems`` is a chapter's workbench, where a reader edits the
  chapter's problems and runs their tests in the page. The renderer checks that the chapter it
  names has problems.
- A ``{literalinclude}`` of a file in this repository gets a bar naming the file, because the
  book's code and queries are quoted from the working tree, and the reader should always be able
  to see which file a block came from. A quoted query can be edited and run in the page.
- A fenced block in the language ``run``, right after a ``{literalinclude}`` of the engine, makes
  that listing editable in the page: the reader changes the code, and the page runs it in place
  of the engine's own, then runs what the block names, a panel's report or some of the engine's
  tests. It becomes an empty marker the page finds; the renderer checks what it names exists.

This file started as a copy of the Parquet book's renderer (``snowch/parquet-book``). That book
shows its reader in Python and Rust side by side in tab sets; this one is Python only, so a tab
set is a node type like any other it does not handle.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from tools.highlight import highlight
from tools.outline import BY_ANCHOR, EXPERIMENTS

ROOT = Path(__file__).resolve().parent.parent
# The panels' file names are the engine's to decide (query_lab.report.panel_name): the figures
# write the JSON and this renderer embeds it, so both must agree on where it lives. The engine
# imports its scan layer, the Parquet book's reader, from the submodule, so both go on the path:
# the site is built by workflows that set no PYTHONPATH.
for path in (ROOT / "external" / "parquet-book" / "python", ROOT / "python"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
from query_lab.figures import QUERY_OF_FRAGMENT  # noqa: E402
from query_lab.report import panel_name  # noqa: E402
from query_lab.timing import TIMINGS, json_name  # noqa: E402

REPO_URL = "https://github.com/snowch/query-engine-book/blob/main/"


class UnknownNodeError(Exception):
    """A node type the renderer does not handle. Raised, never skipped."""


class LabBlockError(Exception):
    """A ``lab`` block that names an experiment or fixture that does not exist."""


#: MyST page slug -> the file this build publishes it as. Filled in by the site build.
PAGES: dict[str, str] = {}

#: The images the rendered pages use, as repository paths, for the site build to copy.
IMAGES: set[str] = set()

#: A reference whose text opens with a chapter label, which the renderer re-derives.
LABELLED = re.compile(r"^(ch\d+|Appendix [A-Z])\b")


def text_of(node) -> str:
    if isinstance(node, dict):
        if node.get("type") in ("text", "inlineCode"):
            return str(node.get("value", ""))
        return "".join(text_of(c) for c in node.get("children", []))
    if isinstance(node, list):
        return "".join(text_of(c) for c in node)
    return ""


def heading_id(node: dict) -> str:
    if node.get("html_id"):
        return str(node["html_id"])
    keep = "".join(c.lower() if c.isalnum() else "-" for c in text_of(node))
    return "-".join(p for p in keep.split("-") if p)


def parse_key_values(value: str, kind: str) -> dict:
    config = {}
    for line in value.splitlines():
        if not line.strip():
            continue
        key, sep, val = line.partition(":")
        if not sep:
            raise LabBlockError(f"{kind} block line has no colon: {line!r}")
        config[key.strip()] = val.strip()
    return config


def parse_lab_block(value: str) -> dict:
    """A ``lab`` block is ``key: value`` lines. Validated here, so a typo fails the build."""
    config = parse_key_values(value, "lab")
    experiment = config.get("experiment")
    if experiment not in EXPERIMENTS:
        raise LabBlockError(f"unknown experiment {experiment!r}; known: {', '.join(EXPERIMENTS)}")
    for fixture in filter(None, (config.get("fixture"), *config.get("fixtures", "").split(","))):
        if not (ROOT / "fixtures" / fixture.strip()).exists():
            raise LabBlockError(f"lab block names fixtures/{fixture.strip()}, which does not exist")
    queries = [config.get("query", ""), *config.get("variants", "").split(",")]
    for query in filter(None, (q.strip() for q in queries)):
        if not (ROOT / "queries" / query).is_file():
            raise LabBlockError(f"lab block names queries/{query}, which does not exist")
    return config


def panel_data(config: dict) -> dict:
    """The JSON the build computed for a panel, or a build failure naming the command to run."""
    path = ROOT / "chapters" / "_generated" / panel_name(config)
    if not path.is_file():
        raise LabBlockError(
            f"no build-time JSON for {config}: add it to PANELS in python/query_lab/figures.py and "
            f"run `make figures` (expected {path.relative_to(ROOT)})"
        )
    return json.loads(path.read_text())


def _script_json(data: dict) -> str:
    """Minified, and safe inside a script element: a "</" in a string cannot end the element."""
    return json.dumps(data, separators=(",", ":")).replace("</", "<\\/")


def _lab(node: dict) -> str:
    config = parse_lab_block(str(node.get("value", "")))
    attrs = " ".join(f'data-{html.escape(k)}="{html.escape(v)}"' for k, v in config.items())
    return (
        f'<div class="lab" {attrs}>'
        f'<script type="application/json" class="lab-data">{_script_json(panel_data(config))}</script>'
        '<p class="lab-fallback">This panel needs JavaScript.</p></div>'
    )


def _timed(node: dict) -> str:
    config = parse_key_values(str(node.get("value", "")), "timed")
    name = config.get("of", "")
    if set(config) != {"of"} or name not in TIMINGS:
        raise LabBlockError(
            f"a timed block names one timing, as `of: <name>`; the timings are {', '.join(TIMINGS)}"
        )
    path = ROOT / "chapters" / "_generated" / json_name(name)
    if not path.is_file():
        raise LabBlockError(
            f"no cases for the timing {name}: run `make figures` (expected {path.relative_to(ROOT)})"
        )
    return (
        f'<div class="timed" data-of="{html.escape(name)}">'
        f'<script type="application/json" class="timed-data">{_script_json(json.loads(path.read_text()))}</script>'
        '<p class="lab-fallback">These cases are timed in your browser, which needs JavaScript.</p></div>'
    )


class RunBlockError(LabBlockError):
    """A ``run`` block that names something to run that does not exist."""


def parse_run_block(value: str) -> dict:
    """A ``run`` block says what to run on the reader's edit of the listing above it: a panel's
    report, as a ``lab`` block names one (and the build must have its JSON, which the page
    compares the edit's answer with); ``script``, a file of the engine run as a script, whose
    printed output the page shows as a notebook shows a cell's; or ``tests``, a file in ``python/tests/``, with an optional
    ``select``, a pytest ``-k`` expression."""
    config = parse_key_values(value, "run")
    if "tests" in config:
        if set(config) - {"tests", "select"}:
            raise RunBlockError(f"a run block with tests takes only tests and select; got {config}")
        if not (ROOT / "python" / "tests" / config["tests"]).is_file():
            raise RunBlockError(f"run block names python/tests/{config['tests']}, which does not exist")
        return config
    if "experiment" in config:
        parse_lab_block(value)
        panel_data(config)
        return config
    if "script" in config:
        if set(config) - {"script"}:
            raise RunBlockError(f"a run block that runs a script takes only script; got {config}")
        path = ROOT / config["script"]
        if not path.is_file() or 'if __name__ == "__main__":' not in path.read_text():
            raise RunBlockError(f"run block runs {config['script']}, which is not a script in the repository")
        return config
    raise RunBlockError(f"a run block names an experiment, tests or a script; got {config}")


def _run(node: dict) -> str:
    config = parse_run_block(str(node.get("value", "")))
    if "tests" in config:
        then = {"tests": config}
    elif "script" in config:
        then = {"script": config["script"]}
    else:
        then = {"report": config, "build": panel_data(config)}
    return f'<script type="application/json" class="run-then">{_script_json(then)}</script>'


def parse_problems_block(value: str) -> str:
    """A ``problems`` block names its chapter: ``chapter: <slug>``. The chapter must have
    problems, so a typo fails the build."""
    config = parse_key_values(value, "problems")
    slug = config.get("chapter", "")
    if set(config) != {"chapter"} or not (ROOT / "exercises" / f"{slug}.py").exists():
        raise LabBlockError(f"a problems block is `chapter: <slug>`, with exercises/<slug>.py; got {config}")
    return slug


def _problems(node: dict) -> str:
    slug = parse_problems_block(str(node.get("value", "")))
    return (
        f'<div class="workbench" data-chapter="{html.escape(slug)}">'
        '<p class="lab-fallback">This workbench needs JavaScript.</p></div>'
    )


def _code(node: dict) -> str:
    lang = node.get("lang") or ""
    if lang == "diagram":
        # A picture drawn in text, not code: no highlighting, and its own line height (book.css).
        return f'<pre class="diagram"><code>{html.escape(str(node.get("value", "")))}</code></pre>'
    # One blank line at most: an excerpt that spans two definitions keeps the two blank lines the
    # formatter puts between them in the source, and on a phone every line counts.
    code = re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", str(node.get("value", "")))
    body = highlight(code, lang)
    cls = f' class="language-{html.escape(lang)}"' if lang else ""
    return f"<pre><code{cls}>{body}</code></pre>"


def _repo_path(include: dict) -> str:
    # MyST gives the path as written in the page, relative to it. Resolve against the
    # repository, so the bar can name the file the way the reader will find it on disk.
    clean = str(include.get("file", ""))
    while clean.startswith("../"):
        clean = clean[3:]
    return clean


def _source_bar(include: dict) -> str:
    clean = _repo_path(include)
    # A walkthrough is a short program the chapter asks you to run and change, not the engine;
    # a query is the SQL a chapter's figures and experiments run.
    if clean.startswith("walkthroughs/"):
        label = "Try it"
    elif clean.startswith("queries/"):
        label = "The query"
    else:
        label = "From the implementation"
    return (
        f'<div class="source-bar"><span class="source-label">{label}</span>'
        f'<a class="source-link" href="{REPO_URL}{html.escape(clean)}" title="Open this file on GitHub">'
        f"<code>{html.escape(clean)}</code></a></div>"
    )


def _xref(node: dict, inner: str) -> str:
    """A link to another part of the book, as a relative URL this build publishes.

    MyST resolves a reference to a page-root URL such as ``/encodings``. The site is served under
    a base path it is not told, so every internal link is rewritten to the relative file this
    build writes. A reference to a chapter whose text opens with a label (``ch05``) gets the
    label re-derived from the outline, so it cannot go stale when chapters move.
    """
    ident = str(node.get("identifier") or "")
    target = BY_ANCHOR.get(ident)
    if target is not None:
        text = text_of(node).strip()
        m = LABELLED.match(text)
        if m:
            inner = html.escape(target.label + text[m.end() :])
        return f'<a class="xref" href="{target.anchor}.html">{inner}</a>'
    url = str(node.get("url") or "")
    path, _, fragment = url.partition("#")
    if not fragment and node.get("type") == "crossReference":
        fragment = str(node.get("html_id") or ident)
    if path.startswith("/"):
        page = PAGES.get(path.strip("/") or "index")
        if page is None:
            raise UnknownNodeError(f"internal link to {url!r}, which this build does not publish")
        href = page + (f"#{fragment}" if fragment else "")
    else:
        href = f"#{fragment}"
    return f'<a class="xref" href="{html.escape(href)}">{inner}</a>'


def _plain(node: dict) -> str:
    """A node's text, without markup: a table heading as a label."""
    if "value" in node and node.get("type") in ("text", "inlineCode"):
        return str(node["value"])
    return "".join(_plain(c) for c in node.get("children", []))


def render(node: dict, footnotes: list | None = None, label: str = "") -> str:
    """Render one node. ``label`` is a table cell's column heading."""
    kind = node.get("type")

    def children() -> str:
        return "".join(render(c, footnotes) for c in node.get("children", []))

    if kind == "text":
        return html.escape(str(node.get("value", "")))
    if kind in ("root", "block"):
        return children()
    if kind == "paragraph":
        return f"<p>{children()}</p>"
    if kind == "heading":
        level = min(max(int(node.get("depth", 2)), 1), 6)
        hid = heading_id(node)
        return (
            f'<h{level} id="{html.escape(hid)}">{children()}'
            f'<a class="anchor" href="#{html.escape(hid)}" aria-label="Link to this section">#</a></h{level}>'
        )
    if kind == "strong":
        return f"<strong>{children()}</strong>"
    if kind == "emphasis":
        return f"<em>{children()}</em>"
    if kind == "inlineCode":
        return f"<code>{html.escape(str(node.get('value', '')))}</code>"
    if kind == "keyboard":
        return f"<kbd>{children()}</kbd>"
    if kind == "break":
        return "<br>"
    if kind == "thematicBreak":
        return "<hr>"
    if kind == "comment":
        return ""
    if kind == "code":
        if node.get("lang") == "lab":
            return _lab(node)
        if node.get("lang") == "problems":
            return _problems(node)
        if node.get("lang") == "timed":
            return _timed(node)
        if node.get("lang") == "run":
            return _run(node)
        return _code(node)
    if kind == "include":
        if node.get("literal"):
            walkthrough = _repo_path(node).startswith("walkthroughs/")
            return (
                (
                    f'<figure class="quoted walkthrough" data-file="{html.escape(_repo_path(node))}">'
                    if walkthrough
                    else f'<figure class="quoted" data-file="{html.escape(_repo_path(node))}">'
                )
                + _source_bar(node)
                + "".join(render(c, footnotes) for c in node.get("children", []))
                + "</figure>"
            )
        # A fragment computed from a query carries the query's name, so the page can say which
        # figures are the book's when the reader runs their own edit of that query.
        query = QUERY_OF_FRAGMENT.get(Path(_repo_path(node)).name)
        attr = f' data-query="{html.escape(query)}"' if query else ""
        return f'<div class="generated"{attr}>{children()}</div>'
    if kind == "blockquote":
        return f"<blockquote>{children()}</blockquote>"
    if kind == "list":
        tag = "ol" if node.get("ordered") else "ul"
        start = node.get("start")
        attr = f' start="{int(start)}"' if tag == "ol" and start not in (None, 1) else ""
        return f"<{tag}{attr}>{children()}</{tag}>"
    if kind == "listItem":
        # A tight list item holds one paragraph; unwrap it so the list does not double-space.
        kids = node.get("children", [])
        if len(kids) == 1 and kids[0].get("type") == "paragraph":
            return f"<li>{''.join(render(c, footnotes) for c in kids[0].get('children', []))}</li>"
        return f"<li>{children()}</li>"
    if kind == "table":
        rows = node.get("children", [])
        head = [r for r in rows if all(c.get("header") for c in r.get("children", []))]
        body = [r for r in rows if r not in head]
        thead = "".join(render(r, footnotes) for r in head)
        # Each body cell carries its column's heading, so a wide table can become one card per row
        # on a narrow screen (web/book.css), with every value labelled, instead of squeezing a
        # sentence into a column one word wide.
        labels = [_plain(c) for c in head[0].get("children", [])] if head else []
        tbody = "".join(
            "<tr>"
            + "".join(
                render(c, footnotes, label=labels[i] if i < len(labels) else "")
                for i, c in enumerate(r.get("children", []))
            )
            + "</tr>"
            for r in body
        )
        wide = ' class="cards"' if len(labels) >= 5 else ""
        return (
            f'<div class="table-wrap"><table{wide}>'
            f"{'<thead>' + thead + '</thead>' if thead else ''}<tbody>{tbody}</tbody></table></div>"
        )
    if kind == "tableRow":
        return f"<tr>{children()}</tr>"
    if kind == "tableCell":
        tag = "th" if node.get("header") else "td"
        align = node.get("align")
        style = f' class="align-{align}"' if align in ("left", "right", "center") else ""
        data = f' data-label="{html.escape(label)}"' if label else ""
        return f"<{tag}{style}{data}>{children()}</{tag}>"
    if kind == "div":
        classes = " ".join(str(node.get("class", "")).split())
        return f'<div class="{html.escape(classes)}">{children()}</div>'
    if kind == "admonition":
        return f'<aside class="admonition {html.escape(str(node.get("kind", "note")))}">{children()}</aside>'
    if kind == "admonitionTitle":
        return f'<p class="admonition-title">{children()}</p>'
    if kind == "link" and node.get("internal"):
        return _xref(node, children())
    if kind == "link":
        url = str(node.get("url", ""))
        ext = url.startswith(("http://", "https://"))
        rel = ' rel="noopener"' if ext else ""
        return f'<a href="{html.escape(url)}"{rel}>{children()}</a>'
    if kind == "crossReference":
        return _xref(node, children())
    if kind == "mystTarget":
        return f'<span id="{html.escape(str(node.get("label", "")))}"></span>'
    if kind == "footnoteReference":
        n = html.escape(str(node.get("enumerator") or node.get("label")))
        return f'<sup class="fn"><a id="fnref-{n}" href="#fn-{n}">{n}</a></sup>'
    if kind == "footnoteDefinition":
        if footnotes is not None:
            footnotes.append(node)
        return ""
    if kind == "image":
        # MyST rewrites an image's URL to a hashed name at the site's root, which breaks under a
        # base path. The path as written is kept in urlSource: the site build copies that file,
        # and every page is published flat at the root, so the path works from any page.
        src = _repo_path({"file": str(node.get("urlSource") or node.get("url", ""))}).lstrip("/")
        IMAGES.add(src)
        alt = html.escape(str(node.get("alt", "")))
        return f'<img src="{html.escape(src)}" alt="{alt}" loading="lazy">'
    if kind == "container":
        return f"<figure>{children()}</figure>"
    if kind == "caption":
        return f"<figcaption>{children()}</figcaption>"
    if kind in ("subscript", "superscript", "delete"):
        tag = {"subscript": "sub", "superscript": "sup", "delete": "del"}[kind]
        return f"<{tag}>{children()}</{tag}>"
    if kind == "abbreviation":
        return f'<abbr title="{html.escape(str(node.get("title", "")))}">{children()}</abbr>'
    raise UnknownNodeError(
        f"no renderer for MyST node type {kind!r}; add a branch to tools/render.py "
        f"(near {json.dumps(node.get('position', {}))})"
    )


def render_page(mdast: dict) -> str:
    """The body of a page, with its footnotes collected at the end."""
    footnotes: list = []
    body = render(mdast, footnotes)
    if footnotes:
        items = "".join(
            f'<li id="fn-{html.escape(str(f.get("enumerator") or f.get("label")))}">'
            f"{''.join(render(c) for c in f.get('children', []))}</li>"
            for f in footnotes
        )
        body += f'<section class="footnotes"><ol>{items}</ol></section>'
    return body
