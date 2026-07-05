"""In-game intents — the only way to mutate a game once it has started.

Each is a small immutable record carrying the acting `seat`. The engine's
`apply(state, intent)` validates and applies exactly one of these.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .melds import MeldKind


@dataclass(frozen=True)
class MeldSpec:
    """One meld to lay: its kind and the ordered card ids (order matters for
    runs — it is the left-to-right sequence)."""

    kind: MeldKind
    card_ids: list[int]


@dataclass(frozen=True)
class DrawStock:
    seat: int


@dataclass(frozen=True)
class DrawDiscard:
    seat: int


@dataclass(frozen=True)
class ClaimFreeCard:
    seat: int


@dataclass(frozen=True)
class PassFreeCard:
    seat: int


@dataclass(frozen=True)
class LayMelds:
    """Lay one or more melds. Before a player has gone out this is the single
    go-out action (must satisfy the contract and total >= 40 points)."""

    seat: int
    melds: list[MeldSpec] = field(default_factory=list)


@dataclass(frozen=True)
class LayOff:
    seat: int
    meld_id: int
    card_id: int


@dataclass(frozen=True)
class RecoverJoker:
    """Lay the exact card a joker represents to take that joker into hand."""

    seat: int
    meld_id: int
    card_id: int


@dataclass(frozen=True)
class Discard:
    seat: int
    card_id: int


@dataclass(frozen=True)
class ReturnDiscard:
    """Cancel a discard pickup: put the taken card back and return to the draw
    step. Only valid while that card hasn't been melded yet."""

    seat: int


Intent = (
    DrawStock
    | DrawDiscard
    | ClaimFreeCard
    | PassFreeCard
    | LayMelds
    | LayOff
    | RecoverJoker
    | Discard
    | ReturnDiscard
)
