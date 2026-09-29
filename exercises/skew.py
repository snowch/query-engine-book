"""Problems for ch16, Skew. Replace each ``raise NotImplementedError`` with your answer, then press
Run the graders.
"""

from __future__ import annotations

from collections.abc import Iterable


def heavy_hitters(keys: Iterable, k: int) -> dict:
    """Problem 16.1: the keys that might be heavy, in one pass, holding at most ``k`` counters.

    Read ``keys`` once. Keep a counter for at most ``k`` keys at a time. For each key: if it has
    a counter, add one; if not and fewer than ``k`` keys have counters, give it one at one;
    otherwise take one from every counter, and drop the counters that reach nought. Return the
    counters left at the end, key to count. Every key that makes up more than a ``1 / (k + 1)``
    share of the keys is certain to be among them.
    """
    raise NotImplementedError("problem 16.1: find the heavy hitters")


def fanouts(counts: dict, rows: int, nodes: int) -> dict:
    """Problem 16.2: over how many nodes to spread each heavy key's rows.

    ``counts`` gives some keys' rows, out of ``rows`` rows spread over ``nodes`` nodes. Spreading
    a key over more nodes evens the load, but its other side's row must be copied to every one.
    Return, for each key in ``counts``, the fewest nodes that leave no more than an even share,
    ``rows / nodes``, of its rows on any one of them; and never more than ``nodes``.
    """
    raise NotImplementedError("problem 16.2: choose the fanouts")
