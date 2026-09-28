"""The book's structure and its rules, held by tests rather than by habit.

Each test here enforces something CLAUDE.md or AUTHORING_GUIDE.md says. If one fails, the page
is wrong or the rule is, and the rule's documentation says which to suspect.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

from tools.outline import APPENDICES, CHAPTERS, EXPERIMENTS, PARTS, UNWRITTEN
from tools.render import LabBlockError, parse_lab_block

ROOT = Path(__file__).resolve().parent.parent
BOOK_PAGES = sorted(
    [ROOT / "index.md"]
    + list((ROOT / "parts").glob("*.md"))
    + list((ROOT / "chapters").glob("*.md"))
    + list((ROOT / "appendices").glob("*.md"))
)
DOCS = [
    ROOT / n for n in ("README.md", "CLAUDE.md", "PLAN.md", "AUTHORING_GUIDE.md", "STYLE.md", "COUNTERS.md")
]
WRITTEN = [c for c in CHAPTERS if UNWRITTEN not in (ROOT / c.path).read_text()]


def fences(text: str):
    """Yield (language, body) for every fenced block."""
    for m in re.finditer(r"^```([^\n]*)\n(.*?)^```\s*$", text, re.M | re.S):
        yield m.group(1).strip(), m.group(2)


def prose(text: str) -> str:
    """The page with its fenced blocks, inline code, link targets and comments removed."""
    text = re.sub(r"^```.*?^```\s*$", "", text, flags=re.M | re.S)
    text = re.sub(r"^%.*$", "", text, flags=re.M)
    text = re.sub(r"\]\([^)]*\)", "]", text)
    text = re.sub(r"^\([\w-]+\)=$", "", text, flags=re.M)
    return re.sub(r"`[^`\n]*`", "", text)


def headings(text: str, level: int) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(rf"^{'#' * level} (.+)$", prose(text), re.M)]


def test_the_table_of_contents_is_the_outline():
    toc = yaml.safe_load((ROOT / "myst.yml").read_text())["project"]["toc"]
    files = [toc[0]["file"]]
    for entry in toc[1:]:
        if "file" in entry:
            files.append(entry["file"])
        files += [c["file"] for c in entry.get("children", [])]
    expected = ["index.md"]
    for part in PARTS:
        expected.append(part.path)
        expected += [c.path for c in CHAPTERS if c.part == part.title]
    expected += [a.path for a in APPENDICES]
    assert files == expected


@pytest.mark.parametrize("chapter", CHAPTERS, ids=lambda c: c.slug)
def test_every_chapter_has_the_ten_part_shape(chapter):
    text = (ROOT / chapter.path).read_text()
    assert headings(text, 2) == list(chapter.shape)
    assert f"({chapter.anchor})=" in text, "the chapter's label is its slug"
    assert f"\ntitle: {chapter.title}\n" in text
    assert f"\n# {chapter.title}\n" in text, "the heading repeats the title, so MyST drops it"


def test_no_identifier_carries_a_chapter_number():
    """A chapter's number is derived from its position. Labels and slugs never contain one."""
    for c in CHAPTERS:
        assert not re.search(r"\d", c.slug), c.slug


@pytest.mark.parametrize("page", BOOK_PAGES, ids=lambda p: str(p.relative_to(ROOT)))
def test_code_is_quoted_by_text_anchor_never_by_line_number(page):
    assert ":lines:" not in page.read_text(), "line numbers rot on the first edit above them"


@pytest.mark.parametrize("page", BOOK_PAGES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_code_is_pasted_into_a_page(page):
    """Python and SQL in a page are quoted from the working tree with {literalinclude}, never
    pasted: the engine from python/, a query from queries/. A shell command is not code the book
    runs, so ``bash`` blocks may be written in place; generated output comes from an {include}."""
    for lang, _ in fences(page.read_text()):
        assert lang not in ("python", "py", "sql", "text", ""), (
            f"a pasted ```{lang or 'block'}: quote it with {{literalinclude}} or {{include}}"
        )


@pytest.mark.parametrize("page", BOOK_PAGES + DOCS, ids=lambda p: p.name)
def test_no_em_dashes(page):
    assert chr(0x2014) not in page.read_text(), "STYLE.md: no em dashes"


BANNED = [r"\bIn this chapter\b", r"\bsimply\b", r"\bobviously\b", r"\bjust\b", r"\bbasically\b"]


@pytest.mark.parametrize("page", BOOK_PAGES, ids=lambda p: str(p.relative_to(ROOT)))
def test_prose_avoids_the_words_style_md_bans(page):
    text = prose(page.read_text())
    found = [p for p in BANNED if re.search(p, text, re.I)]
    assert not found, f"STYLE.md rule 13: {found}"


def glossary() -> list[tuple[str, str]]:
    """Each glossary entry as (term, the anchor of the chapter that introduces it)."""
    text = (ROOT / "appendices" / "glossary.md").read_text()
    entries = re.findall(r"^\*\*(.+?)\.\*\* (.*?)(?=^\*\*|\Z)", text, re.M | re.S)
    out = []
    for term, body in entries:
        chapters = re.findall(r"\]\(#([\w-]+)\)", body)
        assert chapters, f"glossary: {term!r} names no chapter"
        out.append((term, chapters[0]))
    return out


def test_the_glossary_is_in_order_and_names_real_chapters():
    terms = [t for t, _ in glossary()]
    assert terms == sorted(terms, key=str.lower), "keep the glossary alphabetical"
    anchors = {c.anchor for c in CHAPTERS}
    for term, anchor in glossary():
        assert anchor in anchors, f"glossary: {term!r} points at #{anchor}, which is not a chapter"


def uses(term: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(term)}(?:s|es)?\b", prose(text), re.I) is not None


@pytest.mark.parametrize("term, anchor", glossary(), ids=lambda x: x if isinstance(x, str) else "")
def test_no_term_is_used_before_the_chapter_that_introduces_it(term, anchor):
    """A reader meets each term where it is defined, never before. A chapter that needs a term
    early either defines it itself (and the glossary points there) or says it another way."""
    order = [c.anchor for c in CHAPTERS]
    for c in CHAPTERS[: order.index(anchor)]:
        assert not uses(term, (ROOT / c.path).read_text()), (
            f"{c.label} uses {term!r}, which {CHAPTERS[order.index(anchor)].label} introduces"
        )


@pytest.mark.parametrize("term, anchor", glossary(), ids=lambda x: x if isinstance(x, str) else "")
def test_a_written_chapter_defines_the_terms_the_glossary_says_it_does(term, anchor):
    chapter = next(c for c in CHAPTERS if c.anchor == anchor)
    if chapter not in WRITTEN:
        pytest.skip(f"{chapter.label} is not written")
    assert re.search(rf"\*\*{re.escape(term)}\*\*", (ROOT / chapter.path).read_text(), re.I), (
        f"{chapter.label} should introduce {term!r} in bold where it defines it"
    )


def lab_blocks(text: str) -> list[dict]:
    return [parse_lab_block(body) for lang, body in fences(text) if lang == "lab"]


@pytest.mark.parametrize("chapter", CHAPTERS, ids=lambda c: c.slug)
def test_experiments_are_the_ones_the_outline_declares(chapter):
    used = {b["experiment"] for b in lab_blocks((ROOT / chapter.path).read_text())}
    if chapter in WRITTEN:
        assert used == set(chapter.experiments)
    else:
        assert used <= set(chapter.experiments)


def test_every_experiment_is_used_by_some_chapter():
    assert {e for c in CHAPTERS for e in c.experiments} == set(EXPERIMENTS)


def test_a_lab_block_naming_an_unknown_experiment_is_refused():
    with pytest.raises(LabBlockError):
        parse_lab_block("experiment: nonsense")


def test_every_experiment_has_a_mount_and_a_report():
    """A lab block's experiment is drawn by web/lab and computed by query_lab.report."""
    from query_lab.report import EXPERIMENTS as REPORTS

    js = (ROOT / "web" / "lab" / "lab.js").read_text()
    for e in EXPERIMENTS:
        assert re.search(rf"\b{e}: mount", js), f"web/lab/lab.js does not mount {e}"
        assert e in REPORTS, f"query_lab.report has no {e}"


@pytest.mark.parametrize("chapter", CHAPTERS, ids=lambda c: c.slug)
def test_a_chapters_fixtures_exist(chapter):
    for fixture in chapter.fixtures:
        assert (ROOT / "fixtures" / fixture).exists(), fixture


@pytest.mark.parametrize("page", BOOK_PAGES, ids=lambda p: str(p.relative_to(ROOT)))
def test_a_page_includes_only_files_that_exist(page):
    text = page.read_text()
    for m in re.finditer(r"```\{(?:literal)?include\} (\S+)", text):
        assert (page.parent / m.group(1)).resolve().exists(), m.group(1)


def test_the_renderer_and_the_outline_know_the_same_pages():
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build-site.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sources = [p["source"] for p in module.page_list()]
    assert sources[0] == "index.md"
    assert sorted(sources) == sorted(str(p.relative_to(ROOT)) for p in BOOK_PAGES)


def test_the_number_check_catches_a_typed_number():
    spec = importlib.util.spec_from_file_location("verify_numbers", ROOT / "scripts" / "verify-numbers.py")
    vn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vn)
    page = ROOT / "chapters" / "_scratch_test_page.md"
    try:
        page.write_text("---\ntitle: x\n---\n\nThe scan kept 1183 rows.\n\n```\n637 bytes\n```\n")
        found = vn.problems(page)
        assert len(found) == 1 and "1183 rows" in found[0]
        page.write_text("% number-ok: a definition\nA power of 256.\n\nA power of 256.\n")
        assert len(vn.problems(page)) == 1
    finally:
        page.unlink()
