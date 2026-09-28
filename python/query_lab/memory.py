"""Arrow arrays built from raw buffers, read back bit by bit, and gathered through a cache (ch02).

An Arrow array is a few contiguous buffers of bytes and a length. Which buffers depends on the
type:

- a **fixed-width** array (integers, doubles, dates) has a validity bitmap and a values buffer,
  row ``i``'s value at byte ``i * width``;
- a **string** array has a validity bitmap, an offsets buffer of ``n + 1`` 32-bit integers, and a
  data buffer holding every string's bytes end to end: row ``i`` is
  ``data[offsets[i]:offsets[i + 1]]``.

The scan builds every array it hands up with the functions here, so the bytes ch01's peak memory
counted are these buffers. :func:`gather` reads rows in any order through the cache model in
:mod:`query_lab.cache`, which is how ch02 measures what the order costs.
"""

from __future__ import annotations

import struct

import pyarrow as pa

from .cache import Cache

__all__ = [
    "FIXED",
    "array_from",
    "buffer_names",
    "buffer_sizes",
    "fixed_width_array",
    "gather",
    "is_valid",
    "string_array",
    "validity_bitmap",
]

#: For each fixed-width type the engine reads: its width in bytes, and its ``struct`` format,
#: little-endian as Arrow's buffers are.
FIXED = {
    pa.int32(): (4, "<i"),
    pa.int64(): (8, "<q"),
    pa.float64(): (8, "<d"),
    pa.date32(): (4, "<i"),
}


def validity_bitmap(values: list) -> pa.Buffer | None:
    """One bit per row, set where the row holds a value: row ``i`` is bit ``i % 8`` of byte
    ``i // 8``, counting from the least significant bit. An array with no nulls needs no bitmap,
    and Arrow lets it leave the buffer out, so this returns None for one."""
    if all(v is not None for v in values):
        return None
    bits = bytearray((len(values) + 7) // 8)
    for i, v in enumerate(values):
        if v is not None:
            bits[i // 8] |= 1 << (i % 8)
    return pa.py_buffer(bytes(bits))


def is_valid(array: pa.Array, i: int) -> bool:
    """Whether row ``i`` of ``array`` holds a value, read from its validity bitmap by hand.

    A slice of an array shares its parent's buffers and starts ``array.offset`` rows into them, so
    row ``i`` of the slice is bit ``array.offset + i`` of the bitmap.
    """
    bitmap = array.buffers()[0]
    if bitmap is None:
        return True
    bit = array.offset + i
    return bool(memoryview(bitmap)[bit // 8] >> (bit % 8) & 1)


def fixed_width_array(values: list, kind: pa.DataType) -> pa.Array:
    """A fixed-width array from Python values: a validity bitmap, and a values buffer with each
    row's value packed at ``i * width``. A null's slot is there, holding zeros, so every row's
    value stays at the same place."""
    width, fmt = FIXED[kind]
    packed = bytearray(width * len(values))
    for i, v in enumerate(values):
        struct.pack_into(fmt, packed, i * width, 0 if v is None else v)
    nulls = sum(v is None for v in values)
    buffers = [validity_bitmap(values), pa.py_buffer(bytes(packed))]
    return pa.Array.from_buffers(kind, len(values), buffers, null_count=nulls)


def string_array(values: list[str | None]) -> pa.Array:
    """A string array from Python strings: a validity bitmap, the offsets and the data. A null
    takes no bytes of data: its two offsets are equal."""
    data = bytearray()
    offsets = [0]
    for v in values:
        if v is not None:
            data += v.encode()
        offsets.append(len(data))
    nulls = sum(v is None for v in values)
    buffers = [
        validity_bitmap(values),
        pa.py_buffer(struct.pack(f"<{len(offsets)}i", *offsets)),
        pa.py_buffer(bytes(data)),
    ]
    return pa.Array.from_buffers(pa.string(), len(values), buffers, null_count=nulls)


def array_from(values: list, kind: pa.DataType) -> pa.Array:
    """An array of ``kind`` from Python values, built buffer by buffer."""
    if kind == pa.string():
        return string_array(values)
    if kind in FIXED:
        return fixed_width_array(values, kind)
    raise NotImplementedError(f"no builder for {kind}")


def buffer_names(kind: pa.DataType) -> tuple[str, ...]:
    """What each of an array's buffers holds, in the order ``Array.buffers()`` lists them."""
    return ("validity", "offsets", "data") if kind == pa.string() else ("validity", "values")


def buffer_sizes(array: pa.Array) -> dict[str, int | None]:
    """Each buffer's size in bytes, by name; None for a buffer the array leaves out."""
    return {
        name: None if buffer is None else buffer.size
        for name, buffer in zip(buffer_names(array.type), array.buffers(), strict=True)
    }


def gather(array: pa.Array, indices: list[int], cache: Cache) -> pa.Array:
    """Row ``k`` of the result is row ``indices[k]`` of ``array``: a take, written by hand.

    Every byte it reads from ``array`` goes through ``cache``, in the order it reads them: for
    each row, its validity bit (if the array has a bitmap), then its value. A string's value is
    two reads: its two offsets, then its bytes. The result is built fresh, and its writes are not
    counted.
    """
    names = buffer_names(array.type)
    buffers = array.buffers()
    bitmap = buffers[0]
    out = []
    for i in indices:
        row = array.offset + i
        if bitmap is not None:
            cache.read(names[0], row // 8, 1)
        if array.type == pa.string():
            cache.read(names[1], row * 4, 8)
            start, end = struct.unpack_from("<2i", buffers[1], row * 4)
            if end > start:
                cache.read(names[2], start, end - start)
            value = bytes(memoryview(buffers[2])[start:end]).decode()
        else:
            width, fmt = FIXED[array.type]
            cache.read(names[1], row * width, width)
            value = struct.unpack_from(fmt, buffers[1], row * width)[0]
        out.append(value if is_valid(array, i) else None)
    return array_from(out, array.type)
