"""A reader's edit of a quoted listing runs in place of the engine's code, then is undone."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from query_lab import cpu, memory, plans, report
from query_lab.edits import EditError, edited, enclosing_class, module_of
from query_lab.operators import Scan

ROOT = Path(__file__).resolve().parents[2]


def listing(obj) -> str:
    return inspect.getsource(obj)


def test_a_file_names_its_module_and_a_line_its_class():
    assert module_of("python/query_lab/memory.py") == "query_lab.memory"
    source = (ROOT / "python" / "query_lab" / "operators.py").read_text()
    first = next(line for line in source.splitlines() if line.strip().startswith("def against_page("))
    assert enclosing_class(source, first) == "Comparison"
    assert enclosing_class(source, "class Scan(Operator):") is None
    with pytest.raises(EditError):
        enclosing_class(source, "def nothing_like_this():")


def test_an_edited_function_runs_in_its_place_and_the_original_comes_back():
    original = memory.validity_bitmap
    text = listing(memory.validity_bitmap).replace("return None", "return pa.py_buffer(b'edited')", 1)
    with edited(ROOT, "python/query_lab/memory.py", listing(memory.validity_bitmap), text) as names:
        assert names == ["validity_bitmap"]
        assert memory.validity_bitmap([1, 2]).to_pybytes() == b"edited"
    assert memory.validity_bitmap is original


def test_an_edited_method_keeps_super_working_and_the_rest_of_its_class():
    text = listing(cpu.VectorUnit.run).replace("self.values += values", "self.values += 2 * values")
    with edited(ROOT, "python/query_lab/cpu.py", listing(cpu.VectorUnit.run), text):
        unit = cpu.VectorUnit()
        unit.run(3)
        assert unit.values == 6 and unit.counters()["instructions"] == 1
    unit = cpu.VectorUnit()
    unit.run(3)
    assert unit.values == 3


def test_a_function_imported_by_name_elsewhere_is_replaced_there_too():
    source = listing(cpu.select_with_branch)
    text = source.replace("kept.append(i)", "kept.append(-i)")
    with edited(ROOT, "python/query_lab/cpu.py", source, text):
        assert cpu.select_with_branch([1, 2], lambda v: v > 1, cpu.Predictor()) == [-1]
    assert cpu.select_with_branch([1, 2], lambda v: v > 1, cpu.Predictor()) == [1]


def test_an_edited_class_updates_the_class_other_modules_hold():
    source = listing(Scan)
    text = source.replace('super().__init__("Scan"', 'super().__init__("EditedScan"', 1)
    with edited(ROOT, "python/query_lab/operators.py", source, text):
        assert plans.early_march(ROOT).metrics.operator == "EditedScan"
    assert plans.early_march(ROOT).metrics.operator == "Scan"


def test_a_broken_edit_raises_and_leaves_the_engine_as_it_was():
    before = report.run(ROOT, {"experiment": "branches", "column": "amount"})
    source = listing(cpu.select_without_branch)
    with pytest.raises(SyntaxError):
        with edited(ROOT, "python/query_lab/cpu.py", source, source + "\n    return (\n"):
            pass
    with pytest.raises(ZeroDivisionError):
        with edited(ROOT, "python/query_lab/cpu.py", source, source.replace("n = 0", "n = 1 // 0", 1)):
            report.run(ROOT, {"experiment": "branches", "column": "amount"})
    assert report.run(ROOT, {"experiment": "branches", "column": "amount"}) == before


def test_an_error_names_the_line_of_the_edit_it_is_on():
    source = listing(cpu.VectorUnit.run)
    broken = source.replace("self.values += values", "self.values += values +")
    line = next(i for i, text in enumerate(broken.splitlines(), 1) if text.rstrip().endswith("+"))
    with pytest.raises(SyntaxError) as caught:
        with edited(ROOT, "python/query_lab/cpu.py", source, broken):
            pass
    assert caught.value.lineno == line
    failing = source.replace("self.values += values", "self.values += 1 // 0")
    line = next(i for i, text in enumerate(failing.splitlines(), 1) if "1 // 0" in text)
    with pytest.raises(ZeroDivisionError) as caught:
        with edited(ROOT, "python/query_lab/cpu.py", source, failing):
            cpu.VectorUnit().run(1)
    assert caught.traceback[-1].lineno + 1 == line


def test_an_edited_plan_is_the_one_its_registry_runs_until_the_edit_ends():
    book = listing(plans.returned_unit_price)
    edit = book.replace("pricey = Filter(returned,", "pricey = Filter(scan,")
    assert edit != book
    with edited(ROOT, "python/query_lab/plans.py", book, edit):
        assert plans.PLANS["returned_unit_price.sql"] is plans.returned_unit_price
        skipped = plans.plan_for(ROOT, "returned_unit_price.sql").run().num_rows
    assert plans.PLANS["returned_unit_price.sql"].__code__.co_filename.endswith("plans.py")
    assert plans.plan_for(ROOT, "returned_unit_price.sql").run().num_rows < skipped
