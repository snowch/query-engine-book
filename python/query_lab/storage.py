"""Storage that tests rows itself: the scan handed to the storage (ch05).

An object store answers ranges of bytes, so an engine must fetch every byte it might need and
test the rows itself. Some storage can do more: given a file, the columns and the filters, it
reads the file where the file lives and sends back only the rows that pass. What crosses the
network is then the result, not the data it came from.

:class:`ComputingStore` simulates such storage with the book's own scan, run on the storage's
side, and returns the rows as Arrow IPC, the stream format Arrow uses to move batches between
processes. :class:`StorageScan` is the engine's side: one request out, one stream of batches back.
The two sets of counters stay apart: the engine counts what crossed the network, and the storage
counts what it read of its disks.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pyarrow as pa

from .metrics import Metrics
from .operators import Comparison, Operator, Scan


class ComputingStore:
    """A store of Parquet files that can run a scan itself, on the storage's side."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def select(self, key: str, columns: list[str], filters: list[Comparison]) -> tuple[bytes, Metrics]:
        """Scan ``key`` where it lives, with the page index where the file has one, and return the
        rows that pass as an Arrow IPC stream, with the storage's own scan's counters."""
        scan = Scan(self.root / key, columns, filters, page_index=True)
        table = scan.run()
        sink = pa.BufferOutputStream()
        with pa.ipc.new_stream(sink, table.schema) as writer:
            writer.write_table(table)
        return sink.getvalue().to_pybytes(), scan.metrics


class StorageScan(Operator):
    """Hand the whole scan to the storage: one request carries the file, the columns and the
    filters, and the response carries only the rows that pass.

    ``bytes_read`` counts the response, which is every byte that crossed the network. The storage
    decoded more than it sent; what it read of its disks is :attr:`storage`, its own scan's
    counters, reported beside this operator's and never added to them.
    """

    def __init__(
        self, store: ComputingStore, key: str, columns: list[str], filters: list[Comparison] = ()
    ) -> None:
        detail = f"{key}: {', '.join(columns)}"
        if filters:
            detail += f"; {' AND '.join(map(str, filters))}"
        super().__init__("StorageScan", detail + "; in the storage", [])
        self.store = store
        self.key = key
        self.columns = columns
        self.filters = list(filters)
        self.storage: Metrics | None = None
        """The storage's own scan's counters, once the scan has run."""

    def batches(self) -> Iterator[pa.RecordBatch]:
        payload, self.storage = self.store.select(self.key, self.columns, self.filters)
        self.metrics.requests = 1
        self.metrics.bytes_read = len(payload)
        for batch in pa.ipc.open_stream(payload):
            self.take(batch)
            yield self.emit(batch)

    def schema(self) -> pa.Schema:
        return Scan(self.store.root / self.key, self.columns).schema()
