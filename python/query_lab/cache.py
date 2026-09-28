"""A model of a CPU's data cache, small enough to read in one sitting (ch02).

Memory reaches the processor in **cache lines**, fixed-size blocks of consecutive bytes. The
processor keeps the lines it used recently in a small, fast cache. A read of a byte whose line is
in the cache is a **hit**; any other read is a **miss**, and the line has to be fetched from
memory first, pushing the least recently used line out if the cache is full.

The model counts, it does not time: the same reads give the same counts on every machine and in
the browser (COUNTERS.md, *The simulators' counters*). What it leaves out is in ch02's *What this
cannot tell you*: one level of cache instead of three, any line may sit anywhere in it, nothing
is fetched ahead of time, and writes are not counted.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field

#: A line of 64 bytes, as on most processors today, and a cache of 512 of them: 32 KiB, the size
#: of many processors' smallest and fastest data cache.
LINE_BYTES = 64
LINES = 512


@dataclass
class Cache:
    """``lines`` lines of ``line_bytes`` bytes each. A line may sit anywhere in the cache, and the
    one used longest ago is the one pushed out.

    A buffer is known to the model by name, and starts at the start of a line, as Arrow's
    allocator places it, so the counts do not depend on where the buffer happens to be in memory.
    """

    lines: int = LINES
    line_bytes: int = LINE_BYTES
    reads: int = 0
    """Reads asked of the cache: one per call to :meth:`read`, whatever its size."""
    hits: int = 0
    """Lines a read found in the cache."""
    misses: int = 0
    """Lines a read had to fetch from memory."""
    held: OrderedDict = field(default_factory=OrderedDict, repr=False)
    """The lines in the cache, least recently used first."""

    def read(self, buffer: str, offset: int, size: int) -> None:
        """Read ``size`` bytes of ``buffer`` from byte ``offset``: every line they touch."""
        self.reads += 1
        first = offset // self.line_bytes
        last = (offset + size - 1) // self.line_bytes
        for number in range(first, last + 1):
            line = (buffer, number)
            if line in self.held:
                self.hits += 1
                self.held.move_to_end(line)
            else:
                self.misses += 1
                self.held[line] = None
                if len(self.held) > self.lines:
                    self.held.popitem(last=False)

    @property
    def bytes_fetched(self) -> int:
        """The bytes moved from memory into the cache: a whole line for every miss."""
        return self.misses * self.line_bytes

    def counters(self) -> dict[str, int]:
        return {
            "reads": self.reads,
            "hits": self.hits,
            "misses": self.misses,
            "bytes_fetched": self.bytes_fetched,
        }
