"""Graders for ch17's problems. Each expected answer is derived at test time: by checking what a
cut must satisfy, or by stepping a simulated clock. None is stored."""

from __future__ import annotations

import random

import pytest
from stages_and_distributed_execution import cut_stages, finish_time

SPEND = (
    "Sort",
    [("Exchange", [("Final aggregate", [("Exchange", [("Partial aggregate", [("Join", [
        ("Exchange", [("Scan orders", [])]),
        ("Exchange", [("Scan customers", [])]),
    ])])])])])],
)  # fmt: skip


def random_plan(rng: random.Random, names: list[str], depth: int = 0):
    name = f"op{len(names)}"
    names.append(name)
    children = []
    for _ in range(rng.choice([0, 1, 1, 2]) if depth < 5 else 0):
        child = random_plan(rng, names, depth + 1)
        children.append(("Exchange", [child]) if rng.random() < 0.4 else child)
    return (name, children)


def check(plan):
    stages = cut_stages(plan)
    names, exchanges = [], 0

    def walk(node, above):
        nonlocal exchanges
        name, children = node
        if name == "Exchange":
            exchanges += 1
            walk(children[0], ("exchange", above))
            return
        names.append((name, above))
        for c in children:
            walk(c, ("op", name))

    walk(plan, None)
    assert len(stages) == exchanges + 1, (
        f"{exchanges} exchanges make {exchanges + 1} stages, not {len(stages)}"
    )
    where = {n: i for i, s in enumerate(stages) for n in s}
    assert sorted(where) == sorted(n for n, _ in names) and sum(map(len, stages)) == len(names), (
        "every operator in exactly one stage, and no exchange"
    )
    for name, above in names:
        if above is None:
            continue
        kind, detail = above
        if kind == "op":
            assert where[name] == where[detail], f"{name} and {detail} have no exchange between them"
        else:
            op = detail
            while op is not None and op[0] == "exchange":
                op = op[1]
            if op is not None:
                assert where[name] < where[op[1]], f"{name}'s stage must come before the stage that reads it"
    for stage in stages:
        tops = [
            n
            for n in stage
            if not any(a is not None and a[0] == "op" and a[1] in stage for m, a in names if m == n)
        ]
        assert stage[0] == tops[0], f"a stage's top operator comes first: {stage}"


# Problem 17.1 ----------------------------------------------------------------------------------


@pytest.mark.problem("17.1")
def test_problem_17_1_the_chapters_query_has_five_stages():
    stages = check(SPEND) or cut_stages(SPEND)
    assert stages[-1] == ["Sort"]


@pytest.mark.problem("17.1")
def test_problem_17_1_random_plans():
    rng = random.Random(17)
    for _ in range(200):
        check(random_plan(rng, []))


# Problem 17.2 ----------------------------------------------------------------------------------


def stepped(stages) -> int:
    """Finish times found by stepping a clock, one step at a time."""
    started, done, clock = {}, {}, 0
    while len(done) < len(stages):
        for name, (steps, reads) in stages.items():
            if name not in started and all(r in done and done[r] <= clock for r in reads):
                started[name] = clock
            if name in started and name not in done and clock - started[name] >= steps:
                done[name] = clock
        if len(done) < len(stages):
            clock += 1
    return max(done.values(), default=0)


@pytest.mark.problem("17.2")
def test_problem_17_2_the_chapters_query():
    stages = {
        "orders": (5, []),
        "customers": (1, []),
        "join": (4, ["orders", "customers"]),
        "final": (2, ["join"]),
        "sort": (1, ["final"]),
    }
    assert finish_time(stages) == stepped(stages) == 12


@pytest.mark.problem("17.2")
def test_problem_17_2_random_stages():
    rng = random.Random(172)
    for _ in range(200):
        names = [f"s{i}" for i in range(rng.randint(1, 9))]
        stages = {
            n: (rng.randint(0, 6), rng.sample(names[:i], rng.randint(0, min(i, 3))))
            for i, n in enumerate(names)
        }
        assert finish_time(dict(stages)) == stepped(stages), stages


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        cut_stages(("Scan", []))
    with pytest.raises(NotImplementedError):
        finish_time({"a": (1, [])})


def test_the_graders_expectations_can_be_computed():
    assert stepped({"a": (2, []), "b": (3, ["a"])}) == 5
