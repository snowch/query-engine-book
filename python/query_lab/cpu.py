"""A model of two things a processor does to every value a kernel touches (ch06).

**Branch prediction.** A processor starts on the next instructions before it knows which way a
branch (an ``if``, a loop's test) will go. It guesses from how the branch went before. A right
guess costs nothing; a wrong one, a **misprediction**, throws the started work away. The model
keeps, for each branch in the code, a two-bit counter that moves one step towards "taken" when
the branch is taken and one step back when it is not, and predicts "taken" in the top two of its
four states. A branch that goes the same way many times in a row is predicted well; a branch
that goes either way at random is wrong about as often as it goes the less likely way.

**Vector lanes.** A processor's vector instructions (SIMD, single instruction, multiple data)
apply one operation to several values at once, one per **lane** of a wide register. A kernel
over a whole array can fill every lane; code that handles one value at a time uses one lane and
leaves the rest idle.

The model counts, it does not time: the same code over the same values gives the same counts on
every machine and in the browser (COUNTERS.md, *The simulators' counters*). What it leaves out is
in ch06's *What this cannot tell you*.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

#: A vector register of 32 bytes, as AVX2 on x86 processors has, holds four values of eight bytes:
#: four doubles or four 64-bit integers. The model gives every value eight bytes.
LANES = 4


@dataclass
class Predictor:
    """A two-bit saturating counter for each branch in the code, named by the caller."""

    branches: int = 0
    """Branches run."""
    mispredictions: int = 0
    """Branches that went the other way from the counter's guess."""
    state: dict[str, int] = field(default_factory=dict, repr=False)
    """Each branch's counter: 0 and 1 predict not taken, 2 and 3 predict taken."""

    def branch(self, site: str, taken: bool) -> bool:
        """Run the branch ``site`` one way, count whether the guess was wrong, learn, and return
        ``taken``, so the call can sit where the branch's condition would."""
        counter = self.state.get(site, 1)
        self.branches += 1
        if (counter >= 2) != taken:
            self.mispredictions += 1
        self.state[site] = min(3, counter + 1) if taken else max(0, counter - 1)
        return taken

    def counters(self) -> dict[str, int]:
        return {"branches": self.branches, "mispredictions": self.mispredictions}


@dataclass
class VectorUnit:
    """Instructions of ``lanes`` lanes: one instruction computes up to ``lanes`` values."""

    lanes: int = LANES
    instructions: int = 0
    """Instructions run."""
    values: int = 0
    """Values computed: the lanes that did useful work."""

    def run(self, values: int) -> None:
        """Apply one operation to ``values`` values: as many instructions as it takes to cover
        them, the last one perhaps part full."""
        self.instructions += -(-values // self.lanes)
        self.values += values

    def counters(self) -> dict[str, int]:
        return {
            "instructions": self.instructions,
            "lanes_used": self.values,
            "lanes": self.instructions * self.lanes,
        }


# The two ways to find which rows pass a test. The test is a function of one value; the predictor
# counts the branches each way runs. Both return the same positions.


def select_with_branch(values: Sequence, test: Callable[[object], bool], predictor: Predictor) -> list[int]:
    """The positions of the values that pass, found with an ``if``: one branch per value, going
    the way the test went."""
    kept = []
    for i, value in enumerate(values):
        if predictor.branch("the test", test(value)):
            kept.append(i)
        predictor.branch("the loop", i + 1 < len(values))
    return kept


def select_without_branch(
    values: Sequence, test: Callable[[object], bool], predictor: Predictor
) -> list[int]:
    """The positions of the values that pass, found without a branch on the data: every position
    is written to the next free slot, and the slot moves on by the test's result, one or nought.
    Only the loop's own branch is left, and it goes the same way every time but the last."""
    kept = [0] * len(values)
    n = 0
    for i, value in enumerate(values):
        kept[n] = i
        n += int(test(value))
        predictor.branch("the loop", i + 1 < len(values))
    return kept[:n]
