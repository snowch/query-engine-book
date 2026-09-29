"""Problems for ch04, Statistics and pruning. Replace each ``raise NotImplementedError`` with your
answer, then press Run the graders.
"""

from __future__ import annotations


def pages_for(rows: list[tuple[int, int]], pages: list[tuple[int, int]]) -> list[int]:
    """Problem 4.1: the pages of a column that hold any of ``rows``.

    ``rows`` are the rows a scan kept, as ``[start, end)`` ranges in order. ``pages`` are one
    column's pages, as the offset index gives them: each page's rows, as a ``[start, end)``
    range, in order, together covering the row group. Return the positions in ``pages`` of the
    pages that hold at least one kept row, in order. Every column's pages end at different rows,
    so the scan asks this once for each column it reads.
    """
    raise NotImplementedError("problem 4.1: which pages?")


def kept_rows(pages: list[dict], comparisons: list[tuple[str, object]]) -> list[tuple[int, int]]:
    """Problem 4.2: the rows a scan must read, from one column's page index.

    ``pages`` describe one column's pages, in order: each a dict with ``rows``, its
    ``[start, end)`` range of rows, and ``min`` and ``max``, the smallest and largest value in
    the page. ``comparisons`` all test that column, each as ``(op, value)`` with ``op`` one of
    ``=``, ``!=``, ``<``, ``<=``, ``>``, ``>=``; a row must pass them all.

    Keep a page if one value between its ``min`` and ``max`` could pass every comparison at once.
    That is tighter than the book's scan, which keeps a page if each comparison alone could
    pass: for ``x > 8 AND x < 3``, no page can hold a match. Return the kept pages' rows as
    ``[start, end)`` ranges in order, joining ranges that touch.

    The graders refuse the book's own page test (``Comparison.against_page``) and its range
    arithmetic.
    """
    raise NotImplementedError("problem 4.2: kept rows")
