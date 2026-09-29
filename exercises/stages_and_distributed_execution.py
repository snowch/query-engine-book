"""Problems for ch17, Stages and distributed execution. Replace each ``raise NotImplementedError``
with your answer, then press Run the graders.
"""

from __future__ import annotations

#: A plan is a tree of ``(name, children)``: a name, and a list of plans below it. A plan named
#: ``"Exchange"`` is a shuffle, with one child. Every other name is unique within a plan.
Plan = tuple[str, list]


def cut_stages(plan: Plan) -> list[list[str]]:
    """Problem 17.1: the plan's stages, cut at every exchange.

    A stage is the operators between exchanges: everything reachable from an operator without
    passing through an exchange. Return each stage as the names of its operators, the stage's top
    operator first, and the stages in an order in which each comes after every stage it reads
    from, through an exchange. Exchanges belong to no stage.
    """
    raise NotImplementedError("problem 17.1: cut the stages")


def finish_time(stages: dict[str, tuple[int, list[str]]]) -> int:
    """Problem 17.2: when a query's last stage finishes.

    ``stages`` maps each stage to ``(steps, reads)``: the steps it takes, once started, and the
    stages whose output it reads. A stage starts as soon as every stage it reads has finished;
    stages that read nothing start at step nought, and any number of stages can run at once.
    Return the step at which the last one finishes.
    """
    raise NotImplementedError("problem 17.2: find when the query ends")
