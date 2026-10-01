"""A result as text: its first rows, the way a notebook prints a table (ch01)."""

from __future__ import annotations

import pyarrow as pa


def preview(table: pa.Table, rows: int = 5) -> str:
    """How many rows ``table`` has, then its first ``rows`` rows under their column names, each
    column right-aligned to its widest value. A fraction keeps three places."""
    head = table.slice(0, rows).to_pylist()
    cells = [list(table.column_names)]
    cells += [[f"{v:.3f}" if isinstance(v, float) else str(v) for v in r.values()] for r in head]
    widths = [max(len(row[i]) for row in cells) for i in range(len(cells[0]))]
    lines = ["  ".join(c.rjust(w) for c, w in zip(row, widths, strict=True)) for row in cells]
    shown = f"the first {len(head)}" if len(head) < table.num_rows else "all of them"
    return f"{table.num_rows:,} rows; {shown}:\n" + "\n".join(lines)
