"""Problems for ch18, Pushing instead of pulling. Replace each ``raise NotImplementedError`` with
your answer, then press Run the graders.
"""

from __future__ import annotations

import pyarrow as pa

from query_lab.push import Step


class Build(Step):
    """Problem 18.1: the build side of a pushed hash join, which is a sink.

    Keep every row pushed to you, by the value of its ``key`` column, and want every row there is.
    Your pipeline ends here: the probe can use your rows only once the source has run dry, so set
    ``ready`` when you are told to finish. Count each batch you take with ``self.take``.
    """

    def __init__(self, key: str) -> None:
        super().__init__("Build", key, [])
        self.key = key
        self.ready = False

    def push(self, batch: pa.RecordBatch) -> bool:
        raise NotImplementedError("problem 18.1: keep the build side")

    def finish(self) -> None:
        raise NotImplementedError("problem 18.1: say the build side is ready")


class Probe(Step):
    """Problem 18.1: the probe side of a pushed hash join, an operator in the probe's pipeline.

    For each batch pushed to you, find every row's matches in ``build`` by the value of its ``key``
    column, and push one batch on to ``then``: a row for every match, with the probe row's columns
    followed by the build row's columns other than its key. Answer what ``then`` answers. Refuse,
    with a ``RuntimeError``, a batch that arrives before the build side is ready. Count each batch
    with ``self.take`` on its way in and ``self.emit`` on its way out.
    """

    def __init__(self, build: Build, key: str, then: Step) -> None:
        super().__init__("Probe", key, [then])
        self.build = build
        self.key = key

    def push(self, batch: pa.RecordBatch) -> bool:
        raise NotImplementedError("problem 18.1: probe a batch")


class Coalesce(Step):
    """Problem 18.2: gather small batches into batches of at least ``size`` rows.

    Keep the batches pushed to you until together they hold ``size`` rows or more, then push them
    on to ``then`` as one batch, in the order they came. When you are told to finish, push on
    whatever is left, if any rows are, and then finish ``then``. Answer what ``then`` answered the
    last time you pushed to it, and ``True`` before you have pushed anything. Count each batch with
    ``self.take`` on its way in and ``self.emit`` on its way out.
    """

    def __init__(self, size: int, then: Step) -> None:
        super().__init__("Coalesce", f"{size} rows", [then])
        self.size = size

    def push(self, batch: pa.RecordBatch) -> bool:
        raise NotImplementedError("problem 18.2: gather the batches")

    def finish(self) -> None:
        raise NotImplementedError("problem 18.2: push on what is left")
