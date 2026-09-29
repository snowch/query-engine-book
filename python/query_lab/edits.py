"""A reader's edit of a quoted listing, run in place of the engine's own code, then undone.

A page quotes the engine a few lines at a time: a function, a method, a class. When a chapter
lets the reader edit a listing, the page hands this module the file the listing came from, the
listing as the book quoted it, and the reader's text. :func:`edited` runs the text where the
listing lives (in its module, or in the body of the class that holds it), puts what it defines
in place of what the listing defined, and puts the originals back when the block ends, so the
next thing the page runs sees the engine as the book ships it.

Three details make an excerpt behave like the code it replaced:

- A listing indented inside a class is compiled inside a class body, and every function it
  defines has its ``super()`` pointed at the real class.
- A listing that defines a class the module already has updates that class in place, method by
  method, rather than replacing it: other modules hold the class itself, and a listing that
  quotes part of a class leaves the rest as it was.
- A function other modules imported by name is replaced in those modules too.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
import textwrap
import types
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

#: The attributes every class body defines, which an edit never copies onto the real class.
CLASS_BOOKKEEPING = {"__module__", "__qualname__", "__dict__", "__weakref__", "__doc__", "__firstlineno__"}
#: What an attribute had before an edit, when it had nothing.
MISSING = object()


class EditError(Exception):
    """The edit could not be placed: a listing the file does not hold, or a module not found."""


def module_of(file: str) -> str:
    """``python/query_lab/memory.py`` is the module ``query_lab.memory``."""
    path = Path(file)
    if path.parts[0] != "python" or path.suffix != ".py":
        raise EditError(f"{file} is not a module of the engine")
    return ".".join(path.with_suffix("").parts[1:])


def enclosing_class(source: str, first_line: str) -> str | None:
    """The class whose body holds the line ``first_line`` of ``source``, or None at the top level.
    The first line that matches is the listing's, as a quote's text anchor finds it."""
    lines = source.splitlines()
    try:
        number = next(i for i, line in enumerate(lines, 1) if line.rstrip() == first_line.rstrip())
    except StopIteration:
        raise EditError(f"the listing's first line is not in the file: {first_line!r}") from None
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.lineno < number <= node.end_lineno:
            # The innermost class: a nested class would be a class inside this one's range.
            inner = enclosing_class_within(node, number)
            return inner.name
    return None


def enclosing_class_within(node: ast.ClassDef, number: int) -> ast.ClassDef:
    for child in node.body:
        if isinstance(child, ast.ClassDef) and child.lineno < number <= child.end_lineno:
            return enclosing_class_within(child, number)
    return node


def _pointed_at(value, cls: type):
    """``value`` with every ``super()`` inside it resolved against ``cls``: a function compiled in
    a stand-in class body refers to the stand-in, which the real instances are not."""
    if isinstance(value, (staticmethod, classmethod)):
        return type(value)(_pointed_at(value.__func__, cls))
    if isinstance(value, property):
        return property(*(_pointed_at(f, cls) if f else None for f in (value.fget, value.fset, value.fdel)))
    if not isinstance(value, types.FunctionType) or "__class__" not in value.__code__.co_freevars:
        return value
    cells = tuple(
        types.CellType(cls) if name == "__class__" else cell
        for name, cell in zip(value.__code__.co_freevars, value.__closure__, strict=True)
    )
    fn = types.FunctionType(value.__code__, value.__globals__, value.__name__, value.__defaults__, cells)
    fn.__kwdefaults__ = value.__kwdefaults__
    fn.__qualname__ = f"{cls.__qualname__}.{value.__name__}"
    return fn


def _compiled(source: str, file: str, shift: int):
    """``source`` compiled with its line numbers the reader's: ``shift`` lines were put above
    their text, the class line an edit inside a class is compiled under."""
    name = f"<your edit of {file}>"
    try:
        tree = ast.parse(source, name)
    except SyntaxError as error:
        if error.lineno is not None:
            error.lineno -= shift
        raise
    return compile(ast.increment_lineno(tree, -shift), name, "exec")


@contextmanager
def edited(root: Path, file: str, listing: str, text: str) -> Iterator[list[str]]:
    """Run ``text``, the reader's edit of ``listing`` from ``file``, in place of the listing,
    for the length of the block. Yields the names the edit replaced."""
    module = importlib.import_module(module_of(file))
    first = next(line for line in listing.splitlines() if line.strip())
    owner_name = enclosing_class((root / file).read_text(), first)
    code = textwrap.dedent(text)
    undo: list[tuple[object, str, object]] = []

    def put(owner, name: str, value) -> None:
        undo.append((owner, name, owner.__dict__.get(name, MISSING)))
        setattr(owner, name, value)

    def update_class(cls: type, edit: type) -> None:
        for name, value in vars(edit).items():
            if name not in CLASS_BOOKKEEPING:
                put(cls, name, _pointed_at(value, cls))

    try:
        if owner_name is not None:
            cls = getattr(module, owner_name)
            body = textwrap.indent(code, "    ") if code.strip() else "    pass\n"
            space: dict = {}
            exec(_compiled(f"class {owner_name}:\n{body}", file, 1), module.__dict__, space)
            update_class(cls, space[owner_name])
        else:
            space = {}
            exec(_compiled(code, file, 0), module.__dict__, space)
            for name, value in space.items():
                old = module.__dict__.get(name, MISSING)
                if inspect.isclass(value) and inspect.isclass(old):
                    update_class(old, value)
                    continue
                put(module, name, value)
                if inspect.isfunction(old) or inspect.isclass(old):
                    # Modules that imported the old one by name get the new one too.
                    for other in list(sys.modules.values()):
                        if other is module or not getattr(other, "__name__", "").startswith("query_lab"):
                            continue
                        if other.__dict__.get(name) is old:
                            put(other, name, value)
        yield sorted({name for _, name, _ in undo})
    finally:
        for owner, name, old in reversed(undo):
            if old is MISSING:
                delattr(owner, name)
            else:
                setattr(owner, name, old)
