"""The problems' graders are skipped unless you ask for them: ``pytest exercises --problems``.

A problem fails until you solve it, which is its purpose; a suite that went red for an unsolved
exercise would teach everyone to ignore red. CI runs the scaffolding tests beside each problem,
which prove it can be answered, and skips the graders.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser):
    parser.addoption("--problems", action="store_true", help="run the chapter problems' graders")


def pytest_configure(config):
    config.addinivalue_line("markers", "problem(number): a chapter problem's grader, run with --problems")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--problems"):
        return
    skip = pytest.mark.skip(reason="a problem: run with --problems once you have solved it")
    for item in items:
        if item.get_closest_marker("problem"):
            item.add_marker(skip)
