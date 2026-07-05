"""The 11 round contracts and the checker that decides whether a go-out
satisfies the current round."""

from __future__ import annotations

from dataclasses import dataclass

from .melds import MeldKind


@dataclass(frozen=True)
class Requirement:
    kind: MeldKind
    min_len: int

    def label(self) -> str:
        word = "triplet" if self.kind == MeldKind.SET else f"run of {self.min_len}"
        return word


@dataclass(frozen=True)
class Contract:
    round_no: int
    requirements: tuple[Requirement, ...]

    def label(self) -> str:
        from collections import Counter

        parts = Counter(r.label() for r in self.requirements)
        return " + ".join(
            f"{n} {label}" + ("s" if n > 1 and label == "triplet" else "")
            for label, n in parts.items()
        )


_S = MeldKind.SET
_R = MeldKind.RUN


def _req(kind: MeldKind, n: int) -> Requirement:
    return Requirement(kind=kind, min_len=n)


# Round -> required melds (DESIGN.md §3.4).
CONTRACTS: dict[int, tuple[Requirement, ...]] = {
    1: (_req(_S, 3),),
    2: (_req(_R, 4),),
    3: (_req(_R, 5),),
    4: (_req(_S, 3), _req(_S, 3)),
    5: (_req(_R, 4), _req(_S, 3)),
    6: (_req(_R, 4), _req(_R, 4)),
    7: (_req(_S, 3), _req(_S, 3), _req(_S, 3)),
    8: (_req(_S, 3), _req(_S, 3), _req(_R, 4)),
    9: (_req(_R, 4), _req(_R, 4), _req(_S, 3)),
    10: (_req(_R, 4), _req(_R, 4), _req(_R, 4)),
    11: (_req(_S, 3), _req(_S, 3), _req(_S, 3), _req(_R, 4)),
}

TOTAL_ROUNDS = len(CONTRACTS)


def contract_for(round_no: int) -> Contract:
    return Contract(round_no=round_no, requirements=CONTRACTS[round_no])


@dataclass(frozen=True)
class LaidMeld:
    """A meld being laid in a go-out action: its kind and length."""

    kind: MeldKind
    length: int


def satisfies_contract(contract: Contract, laid: list[LaidMeld]) -> bool:
    """Can the laid melds cover every requirement (one meld per requirement)?

    Greedy by descending min_len within each kind: assign the shortest meld that
    still meets each requirement. Extra melds beyond the contract are allowed.
    """
    for kind in (MeldKind.SET, MeldKind.RUN):
        reqs = sorted(
            (r for r in contract.requirements if r.kind == kind), key=lambda r: -r.min_len
        )
        available = sorted((m.length for m in laid if m.kind == kind), reverse=True)
        for req in reqs:
            # take the longest available meld that satisfies this requirement
            idx = next((i for i, length in enumerate(available) if length >= req.min_len), None)
            if idx is None:
                return False
            available.pop(idx)
    return True
