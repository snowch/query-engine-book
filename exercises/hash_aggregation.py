"""Problems for ch07, Hash aggregation. Replace each ``raise NotImplementedError`` with your
answer, then press Run the graders.
"""

from __future__ import annotations


def probes(hashes: list[int], capacity: int) -> int:
    """Problem 7.1: the slots linear probing looks at to insert keys with these ``hashes``, one
    after another, into an empty table of ``capacity`` slots.

    ``capacity`` is a power of two, and larger than the number of keys, so the table never fills
    and never grows. The keys are all different. A key's first slot is its hash's low bits,
    ``hash & (capacity - 1)``; if that slot is taken it tries the next, wrapping from the last slot
    to the first, until it finds an empty one. Count every slot looked at, the empty one included.
    """
    raise NotImplementedError("problem 7.1: how many probes?")


def combine(partials: list[dict]) -> dict:
    """Problem 7.2: the final aggregates of every group, from partial aggregates computed apart.

    Each of ``partials`` is one part of the data, aggregated alone: it maps a group's key to
    ``(count, sum, min, max)`` of a column over that part's rows of the group. A key may appear
    in any number of the parts. Return a dict mapping every key to
    ``(count, sum, min, max, avg)`` over all its rows, where ``avg`` is ``sum / count``.
    """
    raise NotImplementedError("problem 7.2: combine the parts")
