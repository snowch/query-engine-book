"""The renderer refuses what it does not understand, and escapes what it does."""

from __future__ import annotations

import json

import pytest

from tools.highlight import highlight
from tools.render import LabBlockError, RunBlockError, UnknownNodeError, parse_run_block, render, render_page


def test_an_unknown_node_raises_rather_than_vanishing():
    with pytest.raises(UnknownNodeError):
        render({"type": "someNewDirective", "children": []})


def test_a_tab_set_is_not_this_books_markup():
    """The Parquet book shows two languages in tab sets. This book has one, so a tab set is an
    error, not a box with one tab in it."""
    with pytest.raises(UnknownNodeError):
        render({"type": "tabSet", "children": []})


def test_a_lab_block_carries_the_json_the_build_computed():
    html = render(
        {
            "type": "code",
            "lang": "lab",
            "value": "experiment: plan\nquery: returned_unit_price.sql\n"
            "variants: pricier_returns.sql, shipped_unit_price.sql",
        }
    )
    assert 'class="lab"' in html and 'data-experiment="plan"' in html
    data = json.loads(html.split('class="lab-data">', 1)[1].split("</script>", 1)[0])
    assert data["experiment"] == "plan" and data["query"] == "returned_unit_price.sql"
    assert [v["query"] for v in data["variants"]] == ["pricier_returns.sql", "shipped_unit_price.sql"]
    assert "This panel needs JavaScript." in html


def test_a_lab_block_naming_a_missing_query_or_panel_is_refused():
    with pytest.raises(LabBlockError, match="queries/missing.sql"):
        render({"type": "code", "lang": "lab", "value": "experiment: plan\nquery: missing.sql"})


def test_a_problems_block_becomes_a_workbench():
    html = render({"type": "code", "lang": "problems", "value": "chapter: the_plan_is_the_map"})
    assert 'class="workbench" data-chapter="the_plan_is_the_map"' in html
    assert "needs JavaScript" in html
    with pytest.raises(LabBlockError):
        render({"type": "code", "lang": "problems", "value": "chapter: no_such_chapter"})


def test_text_is_escaped():
    assert render({"type": "text", "value": "<b>&"}) == "&lt;b&gt;&amp;"


def test_a_literal_include_names_its_source_file():
    node = {
        "type": "include",
        "literal": True,
        "file": "../python/query_lab/reference.py",
        "children": [{"type": "code", "lang": "python", "value": "def f(): pass"}],
    }
    html = render(node)
    assert "python/query_lab/reference.py" in html and "../" not in html.split("<pre>")[0]
    assert "From the implementation" in html


def test_a_quoted_query_is_labelled_as_one():
    node = {
        "type": "include",
        "literal": True,
        "file": "../queries/returned_unit_price.sql",
        "children": [{"type": "code", "lang": "sql", "value": "SELECT 1"}],
    }
    assert "The query" in render(node)


def test_footnotes_are_collected_at_the_end():
    tree = {
        "type": "root",
        "children": [
            {"type": "paragraph", "children": [{"type": "footnoteReference", "enumerator": "1"}]},
            {"type": "footnoteDefinition", "enumerator": "1", "children": [{"type": "text", "value": "n"}]},
        ],
    }
    html = render_page(tree)
    assert html.index("fnref-1") < html.index('class="footnotes"')


def test_highlighting_colours_sql_and_escapes_it():
    out = highlight("SELECT a FROM t WHERE s = '<x>' -- done", "sql")
    assert '<span class="tok-keyword">SELECT</span>' in out
    assert '<span class="tok-string">&#x27;&lt;x&gt;&#x27;</span>' in out
    assert '<span class="tok-comment">-- done</span>' in out


def test_code_shows_one_blank_line_at_most():
    out = render({"type": "code", "lang": "", "value": "def a():\n    pass\n\n\ndef b():\n    pass"})
    assert "pass\n\ndef b" in out and "\n\n\n" not in out


def test_a_run_block_can_run_a_script_and_nothing_else():
    """Run as a notebook cell runs: what the script prints is the output, with nothing behind it."""
    assert parse_run_block("script: python/query_lab/first_plan.py") == {
        "script": "python/query_lab/first_plan.py"
    }
    with pytest.raises(RunBlockError, match="not a script"):
        parse_run_block("script: python/query_lab/operators.py")
    with pytest.raises(RunBlockError, match="takes only script"):
        parse_run_block("script: python/query_lab/first_plan.py\nselect: projection")
