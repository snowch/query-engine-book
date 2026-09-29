"""Problems for ch11, From SQL to a logical plan. Replace each ``raise NotImplementedError`` with
your answer, then press Run the graders.
"""

from __future__ import annotations

from query_lab import sql
from query_lab.expressions import Expression
from query_lab.sql import Query


class Parser(sql.Parser):
    """The book's parser, which problem 11.1 teaches to read ``BETWEEN`` and ``IN``."""

    def comparison(self) -> Expression:
        """Problem 11.1: a comparison, as the book's parser reads one, and two more.

        ``x BETWEEN a AND b`` is true where ``x >= a`` and ``x <= b``. ``x IN (a, b, c)`` is true
        where ``x`` equals any value in the list, which holds at least one. Either may have
        ``NOT`` before its keyword, as in ``x NOT IN (a, b)``, and is then true where it would
        have been false. Return a tree of the calls the engine already evaluates (``>=``,
        ``<=``, ``=``, ``and``, ``or`` and ``not``), so nothing after the parser changes. The
        book's own ``super().comparison()`` reads the value on the left, with any comparison
        that follows it.
        """
        raise NotImplementedError("problem 11.1: read BETWEEN and IN")


def resolve_ordinals(query: Query) -> Query:
    """Problem 11.2: bind ``GROUP BY 1`` and ``ORDER BY 2 DESC`` to what they name.

    A whole number in ``GROUP BY`` or ``ORDER BY`` names an item of the ``SELECT`` list by its
    place in the list, counting from one. Return the query with each such number replaced: in
    ``GROUP BY``, by that item's expression; in ``ORDER BY``, by a ``Column`` named as the item
    is handed up, its alias or else :func:`query_lab.planner.name_of` its expression, keeping
    the key's direction. Raise ``ValueError`` for a number that names no item. Change nothing
    else, and leave ``query`` itself as it was.
    """
    raise NotImplementedError("problem 11.2: bind the ordinals")
