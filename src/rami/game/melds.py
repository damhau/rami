"""Melds: sets (triplettes) and runs (suites), with joker logic.

A meld stores only its physical cards; what each joker *represents* is derived
deterministically from the meld's contents (no stored state to drift). This is
how joker auto-reassignment (§3.9 of DESIGN.md) and recovery are kept honest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from rami.core.exceptions import IllegalMove

from .cards import (
    ALL_SUITS,
    MIN_RANK,
    NUM_DECKS,
    RANK_ACE,
    RANK_ACE_HIGH,
    Card,
    Suit,
    rank_points,
)


class MeldKind(StrEnum):
    SET = "set"  # triplette: >=3 same rank
    RUN = "run"  # suite: >=3 consecutive, same suit


@dataclass(frozen=True)
class ReprCard:
    """The concrete card a joker currently stands in for."""

    suit: Suit
    rank: int  # 1..14 (14 = Ace high)


@dataclass
class Meld:
    id: int
    kind: MeldKind
    cards: list[Card]
    owner_seat: int
    represents: dict[int, ReprCard] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        """Recompute joker representations from current cards."""
        self.represents = joker_representations(self.kind, self.cards)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def _split(cards: list[Card]) -> tuple[list[Card], list[Card]]:
    real = [c for c in cards if not c.is_joker]
    jokers = [c for c in cards if c.is_joker]
    return real, jokers


def set_rank(cards: list[Card]) -> int | None:
    """The shared rank of a set, or None if undefined/invalid."""
    real, _ = _split(cards)
    if not real:
        return None
    ranks = {c.rank for c in real}
    if len(ranks) != 1:
        return None
    return real[0].rank


def is_valid_set(cards: list[Card]) -> bool:
    if len(cards) < 3:
        return False
    real, _ = _split(cards)
    if not real:
        return False
    if set_rank(cards) is None:
        return False
    # No more copies of a suit than there are decks.
    per_suit: dict[Suit, int] = {}
    for c in real:
        assert c.suit is not None
        per_suit[c.suit] = per_suit.get(c.suit, 0) + 1
        if per_suit[c.suit] > NUM_DECKS:
            return False
    return True


def run_suit(cards: list[Card]) -> Suit | None:
    real, _ = _split(cards)
    if not real:
        return None
    suits = {c.suit for c in real}
    if len(suits) != 1:
        return None
    return real[0].suit


def _run_start(cards: list[Card]) -> int | None:
    """Find the starting rank of the run given the card order, or None.

    Each position i must hold rank `start + i`. A real Ace may be low (1) or
    high (14). No wrap-around (a single run cannot span both Ace ends).
    """
    real, _ = _split(cards)
    if not real:
        return None
    if run_suit(cards) is None:
        return None

    n = len(cards)
    candidate_starts: set[int] | None = None
    for i, c in enumerate(cards):
        if c.is_joker:
            continue
        assert c.rank is not None
        options = {RANK_ACE - i, RANK_ACE_HIGH - i} if c.rank == RANK_ACE else {c.rank - i}
        candidate_starts = options if candidate_starts is None else (candidate_starts & options)
        if not candidate_starts:
            return None

    if not candidate_starts:
        return None

    valid: list[int] = []
    for start in candidate_starts:
        end = start + n - 1
        if start < MIN_RANK or end > RANK_ACE_HIGH:
            continue
        if start == MIN_RANK and end == RANK_ACE_HIGH:
            continue  # full circle / both Ace ends — not allowed
        valid.append(start)
    if not valid:
        return None
    return min(valid)


def is_valid_run(cards: list[Card]) -> bool:
    if len(cards) < 3:
        return False
    real, _ = _split(cards)
    if not real:
        return False
    return _run_start(cards) is not None


def is_valid_meld(kind: MeldKind, cards: list[Card]) -> bool:
    return is_valid_set(cards) if kind == MeldKind.SET else is_valid_run(cards)


def validate_meld(kind: MeldKind, cards: list[Card]) -> None:
    if not is_valid_meld(kind, cards):
        raise IllegalMove(f"not a valid {kind.value}: {[c.label for c in cards]}")


# --------------------------------------------------------------------------- #
# Joker representation
# --------------------------------------------------------------------------- #


def joker_representations(kind: MeldKind, cards: list[Card]) -> dict[int, ReprCard]:
    if kind == MeldKind.SET:
        return _set_joker_reprs(cards)
    return _run_joker_reprs(cards)


def _set_joker_reprs(cards: list[Card]) -> dict[int, ReprCard]:
    rank = set_rank(cards)
    real, jokers = _split(cards)
    if rank is None or not jokers:
        return {}
    per_suit: dict[Suit, int] = dict.fromkeys(ALL_SUITS, 0)
    for c in real:
        assert c.suit is not None
        per_suit[c.suit] += 1
    # Open slots, missing suits first, then second-deck copies.
    open_slots: list[Suit] = []
    for copy in range(NUM_DECKS):
        for suit in ALL_SUITS:
            if per_suit[suit] <= copy:
                open_slots.append(suit)
    out: dict[int, ReprCard] = {}
    for joker, suit in zip(jokers, open_slots, strict=False):
        out[joker.id] = ReprCard(suit=suit, rank=rank)
    return out


def _run_joker_reprs(cards: list[Card]) -> dict[int, ReprCard]:
    start = _run_start(cards)
    suit = run_suit(cards)
    if start is None or suit is None:
        return {}
    out: dict[int, ReprCard] = {}
    for i, c in enumerate(cards):
        if c.is_joker:
            out[c.id] = ReprCard(suit=suit, rank=start + i)
    return out


def repr_matches_card(rep: ReprCard, card: Card) -> bool:
    """Does `card` (a real card) match what a joker represents?"""
    if card.is_joker or card.suit != rep.suit:
        return False
    if rep.rank == RANK_ACE_HIGH:
        return card.rank == RANK_ACE
    return card.rank == rep.rank


# --------------------------------------------------------------------------- #
# Points
# --------------------------------------------------------------------------- #


def meld_points(meld: Meld) -> int:
    """Total laid value of a meld; a joker counts as the card it represents."""
    total = 0
    reps = meld.represents
    for c in meld.cards:
        if c.is_joker:
            rep = reps.get(c.id)
            total += rank_points(rep.rank) if rep is not None else 0
        else:
            assert c.rank is not None
            total += rank_points(c.rank)
    return total


def cards_points(cards: list[Card], kind: MeldKind) -> int:
    """Laid value of a not-yet-built meld (used to score a go-out action)."""
    return meld_points(Meld(id=-1, kind=kind, cards=list(cards), owner_seat=-1))


# --------------------------------------------------------------------------- #
# Laying off onto an existing meld
# --------------------------------------------------------------------------- #


def try_lay_off(meld: Meld, card: Card) -> list[Card] | None:
    """Return the new card list if `card` legally extends `meld`, else None."""
    if meld.kind == MeldKind.SET:
        candidate = [*meld.cards, card]
        return candidate if is_valid_set(candidate) else None
    # Run: try both ends.
    for candidate in ([card, *meld.cards], [*meld.cards, card]):
        if is_valid_run(candidate):
            return candidate
    return None
