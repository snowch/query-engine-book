"""The no-code route preserves the reports' evidence and the editable listings' wiring."""

import hashlib
import json
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tools.reading import worked_result
from tools.render import LabBlockError, render, render_page

ROOT = Path(__file__).resolve().parent.parent
REPORTS = sorted((ROOT / "chapters/_generated").glob("panel-*.json"))


class Text(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.parts = []
        self.feed(html)

    def handle_data(self, data):
        self.parts.append(data)


@pytest.mark.parametrize("path", REPORTS, ids=lambda p: p.stem)
def test_static_evidence_preserves_the_generated_measurements(path):
    data = json.loads(path.read_text())
    html = worked_result(data)
    visible = " ".join(Text(html).parts)
    assert data["engine"] in visible
    assert "<script" not in html
    if data["experiment"] == "measure":
        for case in data["cases"]:
            assert case["label"] in visible
            for value in [case["measured"], case["reference"]["value"], *[v for _, v in case["counters"]]]:
                assert f"{value:,}" in visible if isinstance(value, (int, float)) else str(value) in visible
        if data.get("chart"):
            for series in data["chart"]["series"]:
                assert series["label"] in visible
                for x, y in series["points"]:
                    assert f"{x:,}" in visible and f"{y:,}" in visible
    elif data["experiment"] == "pruning":
        assert html.count('class="unit-read"') == sum(f["units_read"] for f in data["files"])
        for file in data["files"]:
            for key in ["rows_decoded", "rows_out", "bytes_read", "requests"]:
                assert f"{file[key]:,}" in visible
    elif data["experiment"] == "gather":
        for gather in data["gathers"]:
            for key in ["reads", "hits", "misses", "bytes_fetched"]:
                assert f"{gather[key]:,}" in visible
    elif data["experiment"] == "branches":
        for case in data["cases"]:
            for key in ["kept", "branches", "mispredictions"]:
                assert f"{case[key]:,}" in visible
    else:

        def check(plan):
            assert f"{plan['result_rows']:,}" in visible

            def walk(node):
                assert node["operator"] in visible
                assert f"{node['rows_out']:,}" in visible
                for child in node["children"]:
                    walk(child)

            walk(plan["root"])
            for variant in plan["variants"]:
                check(variant)

        check(data)


def test_saved_script_output_is_the_actual_unmodified_example():
    data = json.loads((ROOT / "chapters/_generated/script-first-plan.json").read_text())
    source = ROOT / "python/query_lab/first_plan.py"
    assert data["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    run = subprocess.run([sys.executable, str(source)], cwd=ROOT, capture_output=True, text=True, check=True)
    assert data["stdout"] == run.stdout


def test_checkpoints_escape_content_and_require_both_parts():
    html = render({"type": "code", "lang": "checkpoint", "value": "question: Why <script>?\nanswer: A & B"})
    assert "Why &lt;script&gt;?" in html and "A &amp; B" in html
    assert "<details>" in html and " open" not in html
    with pytest.raises(LabBlockError):
        render({"type": "code", "lang": "checkpoint", "value": "question: Why?"})


def test_a_listing_can_run_a_different_script_without_losing_its_output_or_marker():
    html = render_page(
        {
            "type": "root",
            "children": [
                {
                    "type": "block",
                    "children": [
                        {
                            "type": "include",
                            "literal": True,
                            "file": "../python/query_lab/operators.py",
                            "children": [{"type": "code", "lang": "python", "value": "class Scan: pass"}],
                        }
                    ],
                },
                {
                    "type": "block",
                    "children": [
                        {"type": "code", "lang": "run", "value": "script: python/query_lab/first_plan.py"}
                    ],
                },
            ],
        }
    )
    assert html.count('class="optional code-disclosure"') == 1
    assert 'class="worked-result script-result"' in html
    assert '</figure><script type="application/json" class="run-then">' in html
    assert html.index("Example output") < html.index("<details")
