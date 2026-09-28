"""Problems for ch02, Batches in memory. Replace each ``raise NotImplementedError`` with your
answer, then press Run the graders.
"""

from __future__ import annotations

import struct  # noqa: F401  (you will want it)

import pyarrow as pa

from query_lab.cache import Cache


def compact(array: pa.Array) -> pa.Array:
    """Problem 2.1: a copy of ``array`` whose buffers start at its first row.

    ``array`` is an ``int64`` array, and often a slice of a longer one: its buffers are its
    parent's, and its first row is ``array.offset`` rows into them. Return an array with the same
    values and nulls whose offset is zero and whose buffers hold nothing but its own rows:

    - a values buffer of exactly eight bytes per row;
    - no validity bitmap if the array has no nulls; otherwise one of exactly one byte per eight
      rows, rounded up, with row ``i`` at bit ``i % 8`` of byte ``i // 8``, and every bit past the
      last row zero.

    Build it from the buffers with ``pa.py_buffer`` and ``pa.Array.from_buffers``. The graders
    refuse ``pa.array``, ``pa.concat_arrays``, ``pyarrow.compute.take`` and the book's builders
    in ``query_lab.memory``: the point is to move the bits yourself.
    """
    raise NotImplementedError("problem 2.1: compact a slice")


def gather_in_order(array: pa.Array, indices: list[int], cache: Cache) -> pa.Array:
    """Problem 2.2: the same result as ``query_lab.memory.gather(array, indices, cache)``, reading
    ``array`` in the order its rows are stored.

    ``array`` is a fixed-width array with no nulls; ``query_lab.memory.FIXED`` gives its width
    in bytes. Row ``k`` of the result is row ``indices[k]`` of ``array``, as for a
    gather, but read the rows in increasing position, whatever order ``indices`` asks for them
    in, and put each value where the result needs it. Read each row once for every time
    ``indices`` names it, with ``cache.read("values", byte_offset, width)``, where
    ``byte_offset`` counts from the start of the values buffer (mind ``array.offset``).

    The graders check your result, the order of your reads, and the lines the cache fetched.
    They refuse ``query_lab.memory.gather`` and pyarrow's ``take``.
    """
    raise NotImplementedError("problem 2.2: read in order")
