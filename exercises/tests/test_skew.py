"""Graders for ch16's problems. Each expected answer is derived at test time: by counting the keys,
or by sending the orders to simulated nodes. None is stored."""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from skew import fanouts, heavy_hitters

from query_lab.distributed import node_of

ROOT = Path(__file__).resolve().parents[2]
ORDERS = ROOT / "fixtures" / "orders-sorted.parquet"


def customers() -> list[int]:
    return pq.read_table(ORDERS, columns=["customer_id"]).column(0).to_pylist()


# Problem 16.1 ----------------------------------------------------------------------------------


@pytest.mark.problem("16.1")
@pytest.mark.parametrize("k", [1, 3, 5, 10, 50])
def test_problem_16_1_every_heavy_key_is_found_with_k_counters(k):
    keys = customers()
    found = heavy_hitters(iter(keys), k)
    assert len(found) <= k
    counts = Counter(keys)
    for key, n in counts.items():
        if n > len(keys) / (k + 1):
            assert key in found, f"customer {key} has {n} of {len(keys)} orders, and was missed"
    for key, c in found.items():
        assert counts[key] - len(keys) / (k + 1) <= c <= counts[key], f"customer {key}: counter {c}"


@pytest.mark.problem("16.1")
def test_problem_16_1_random_streams():
    rng = random.Random(16)
    for _ in range(100):
        keys = [rng.choice("aaaabbc" + "defghij"[: rng.randint(0, 7)]) for _ in range(rng.randint(0, 60))]
        k = rng.randint(1, 4)
        found = heavy_hitters(keys, k)
        assert len(found) <= k
        for key, n in Counter(keys).items():
            if n > len(keys) / (k + 1):
                assert key in found, f"{keys}, k = {k}: {key!r} missed"


# Problem 16.2 ----------------------------------------------------------------------------------


def spread(keys: list[int], fanout: dict, nodes: int) -> list[int]:
    """The rows each node gets when each key in ``fanout`` is salted over that many nodes."""
    load = [0] * nodes
    seen: Counter = Counter()
    for k in keys:
        salt = seen[k] % fanout.get(k, 1)
        seen[k] += 1
        load[(node_of(k, nodes) + salt) % nodes] += 1
    return load


@pytest.mark.problem("16.2")
@pytest.mark.parametrize("nodes", [4, 8, 16, 32])
def test_problem_16_2_no_heavy_key_leaves_more_than_a_share_on_a_node(nodes):
    keys = customers()
    counts = {k: n for k, n in Counter(keys).most_common(5)}
    chosen = fanouts(dict(counts), len(keys), nodes)
    assert set(chosen) == set(counts)
    share = len(keys) / nodes
    for k, f in chosen.items():
        assert 1 <= f <= nodes
        assert counts[k] / f <= share or f == nodes, f"customer {k}: {counts[k]} rows over {f} nodes"
        assert f == 1 or counts[k] / (f - 1) > share, f"customer {k}: {f} nodes, when fewer would do"
    # On few nodes a salted key can land where another heavy key already is; on many it cannot
    # help but spread.
    if nodes >= 16:
        assert max(spread(keys, chosen, nodes)) < max(spread(keys, {}, nodes))


# Scaffolding: CI runs these. They prove each problem can be answered and is not answered yet.


def test_the_stubs_are_unsolved():
    with pytest.raises(NotImplementedError):
        heavy_hitters([1, 1, 2], 1)
    with pytest.raises(NotImplementedError):
        fanouts({1: 10}, 20, 4)


def test_the_graders_expectations_can_be_computed():
    assert len(customers()) > 0
    assert sum(spread([1, 1, 2], {1: 2}, 3)) == 3
