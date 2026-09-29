"""Problems for ch05, Where work happens. Replace each ``raise NotImplementedError`` with your
answer, then press Run the graders.
"""

from __future__ import annotations

import datetime as dt  # noqa: F401  (you will want it)
import struct  # noqa: F401  (you will want it)


def files_to_open(metadata: dict, comparisons: list[tuple[str, str, object]]) -> list[str]:
    """Problem 5.1: the files of a table that might hold a row passing every comparison, decided
    from the table's metadata alone, without opening any file.

    ``metadata`` is the table's metadata, as ``metadata.json`` holds it: under ``"files"``, a list
    of the table's files in order, each with its ``"path"`` and, under ``"bounds"``, each column's
    ``"lower"`` and ``"upper"`` bounds, PLAIN-encoded and written as hex, with the ``"comparator"``
    that orders them: ``I32`` and ``I64`` are little-endian signed integers of four and eight bytes,
    ``F64`` a little-endian double, and ``BYTES`` a UTF-8 string. A date column is ``I32``: the days
    since 1970-01-01.

    ``comparisons`` are ``(column, op, value)``, with ``op`` one of ``=``, ``!=``, ``<``, ``<=``,
    ``>``, ``>=``, and ``value`` an int, a float, a str or a date. Return the paths of the files to
    open, in the metadata's order. Keep a file unless its bounds rule out every row: a wrong skip
    loses rows, and the graders count the files you open for nothing.

    The graders refuse the book's own decision (``TableScan.ruled_out``, ``Comparison.against_bounds``
    and the Parquet book's ``against_bounds``).
    """
    raise NotImplementedError("problem 5.1: which files?")


def months_to_read(paths: list[str], start: dt.date, end: dt.date) -> list[str]:
    """Problem 5.2: the files of a table in Hive's layout that a query for dates from ``start`` up
    to but not including ``end`` must read, decided from the paths alone.

    Each path is a file of the table, in a directory that names the month its rows belong to, as
    ``month=2024-03/part-0.parquet``. Return the paths whose month holds at least one day in the
    range, in the order given. Read nothing but the paths: this is what a reader can decide before
    it has any metadata at all.
    """
    raise NotImplementedError("problem 5.2: which directories?")
