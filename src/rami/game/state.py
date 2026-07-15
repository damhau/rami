"""Game state: phases, per-player state, the whole-table `GameState`, and the
`Event` records the engine emits."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .cards import Card
from .melds import Meld


class Phase(StrEnum):
    LOBBY = "lobby"
    AWAIT_DRAW = "await_draw"
    AWAIT_DISCARD = "await_discard"
    ROUND_OVER = "round_over"
    GAME_OVER = "game_over"


@dataclass
class PlayerState:
    seat: int
    name: str
    hand: list[Card] = field(default_factory=list)
    has_gone_out: bool = False
    ready: bool = False
    round_score: int = 0
    total_score: int = 0


@dataclass
class FreeCardOffer:
    """An in-progress 'carte gratuite' chain after the active player drew from
    stock (and thereby refused the visible discard)."""

    pending_seats: list[int]  # seats still to decide, in turn order
    resume_seat: int  # active player to resume once the chain resolves


@dataclass
class Event:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class GameState:
    players: list[PlayerState]
    phase: Phase = Phase.LOBBY
    round_no: int = 0
    dealer_seat: int = 0
    turn_seat: int = 0

    stock: list[Card] = field(default_factory=list)
    discard: list[Card] = field(default_factory=list)  # top is the last element
    table_melds: list[Meld] = field(default_factory=list)

    next_meld_id: int = 0
    taken_from_discard_id: int | None = None  # card that must be laid this turn
    free_card: FreeCardOffer | None = None
    # True only during the round's opening turn (before the starter's first draw);
    # gates the 2-player opening free card (§3.7).
    opening_turn: bool = False

    rng_seed: int = 0
    shuffle_count: int = 0

    last_round_scores: dict[int, int] = field(default_factory=dict)

    # -- convenience ------------------------------------------------------- #

    def player(self, seat: int) -> PlayerState:
        return self.players[seat]

    @property
    def num_players(self) -> int:
        return len(self.players)

    def meld(self, meld_id: int) -> Meld | None:
        return next((m for m in self.table_melds if m.id == meld_id), None)
