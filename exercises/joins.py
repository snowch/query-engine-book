"""Problems for ch08, Joins. Replace each ``raise NotImplementedError`` with your answer, then
press Run the graders.
"""

from __future__ import annotations

from query_lab.aggregate import hash_key  # noqa: F401  (you will want it)


def merge_join(left: list[tuple], right: list[tuple]) -> list[tuple]:
    """Problem 8.1: join two inputs already sorted by their key, without a hash table.

    ``left`` and ``right`` are lists of ``(key, value)`` pairs, each sorted by key; a key may
    appear any number of times on either side. Return ``(key, left value, right value)`` for
    every pair of a left row and a right row with the same key: keys in ascending order, and
    within a key, the left rows in their order, each paired with the right rows in theirs. Walk
    both lists once, from the front, as a merge does; never compare every row with every other.
    """
    raise NotImplementedError("problem 8.1: merge the two sides")


def bloom(keys: list, bits: int, hashes: int) -> int:
    """Problem 8.2, first half: a Bloom filter of ``keys``: ``bits`` bits, held as one int, with
    bit ``b`` set for every key and every ``i`` in ``range(hashes)``, where
    ``b = hash_key((i, key)) % bits``."""
    raise NotImplementedError("problem 8.2: build the filter")


def might_contain(filter_bits: int, key, bits: int, hashes: int) -> bool:
    """Problem 8.2, second half: False only if ``key`` is certainly not among the filter's keys:
    one of its bits is not set. True means it might be."""
    raise NotImplementedError("problem 8.2: test a key")
