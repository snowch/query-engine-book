"""Problems for ch15, Partitioning and shuffle. Replace each ``raise NotImplementedError`` with
your answer, then press Run the graders.
"""

from __future__ import annotations

import pyarrow as pa


def already_placed(parts: list[pa.Table], key: str) -> bool:
    """Problem 15.1: whether a shuffle on ``key`` would send nothing.

    ``parts`` are the nodes' rows, node 0 first. Return True when every row is already on the node
    its key belongs to, :func:`query_lab.distributed.node_of`, so that an aggregate or a join on
    ``key`` can skip the shuffle; False if any row is not.
    """
    raise NotImplementedError("problem 15.1: check the placement")


def choose_join(probe_bytes: int, build_bytes: int, nodes: int) -> str:
    """Problem 15.2: ``"broadcast"`` or ``"shuffle"``, whichever sends fewer bytes.

    The probe side is spread evenly over ``nodes`` nodes; the build side is held whole by one of
    them. Broadcasting sends the build side to every other node. Shuffling sends each side's rows
    to the node their key belongs to, and a row stays put only when it is already there, as it is
    for about one row in ``nodes``. Estimate both from the sizes, and return the cheaper.
    """
    raise NotImplementedError("problem 15.2: choose the join")
