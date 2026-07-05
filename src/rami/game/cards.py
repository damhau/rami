"""Cards, the 110-card deck, and point values."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum

# Ranks are 1..13 with Ace = 1, Jack = 11, Queen = 12, King = 13.
# In a run the Ace may additionally act as 14 (high), with no wrap-around.
RANK_ACE = 1
RANK_JACK = 11
RANK_QUEEN = 12
RANK_KING = 13
RANK_ACE_HIGH = 14
MIN_RANK = 1
MAX_RANK = 13

NUM_DECKS = 2
NUM_JOKERS = 6

# Point value of each rank when scored in hand (and of the card a joker
# represents when it is laid in a meld).
RANK_POINTS: dict[int, int] = {
    1: 11,  # Ace
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    6: 6,
    7: 7,
    8: 8,
    9: 9,
    10: 10,
    11: 10,  # Jack
    12: 10,  # Queen
    13: 10,  # King
}

JOKER_HAND_POINTS = 25

_RANK_LABELS: dict[int, str] = {1: "A", 11: "J", 12: "Q", 13: "K", 14: "A"}


class Suit(StrEnum):
    SPADES = "S"
    HEARTS = "H"
    DIAMONDS = "D"
    CLUBS = "C"


ALL_SUITS: tuple[Suit, ...] = (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)


@dataclass(frozen=True)
class Card:
    """A single physical card. `id` is unique across the whole deck."""

    id: int
    suit: Suit | None = None
    rank: int | None = None
    is_joker: bool = False
    deck_id: int = 0

    def __post_init__(self) -> None:
        if self.is_joker:
            if self.suit is not None or self.rank is not None:
                raise ValueError("a joker has no suit or rank")
        elif self.suit is None or self.rank is None:
            raise ValueError("a non-joker needs both suit and rank")

    @property
    def label(self) -> str:
        if self.is_joker:
            return "★"
        assert self.rank is not None
        assert self.suit is not None
        rank = _RANK_LABELS.get(self.rank, str(self.rank))
        return f"{rank}{self.suit.value}"


def rank_label(rank: int) -> str:
    return _RANK_LABELS.get(rank, str(rank))


def card_hand_value(card: Card) -> int:
    """Point value of a card left in hand at the end of a round."""
    if card.is_joker:
        return JOKER_HAND_POINTS
    assert card.rank is not None
    return RANK_POINTS[card.rank]


def rank_points(rank: int) -> int:
    """Points for a (possibly Ace-high) rank — used for melded-joker value."""
    if rank == RANK_ACE_HIGH:
        return RANK_POINTS[RANK_ACE]
    return RANK_POINTS[rank]


def build_deck(rng: random.Random) -> list[Card]:
    """Build and shuffle the 110-card deck: two 52-card decks + 6 jokers."""
    cards: list[Card] = []
    cid = 0
    for deck_id in range(NUM_DECKS):
        for suit in ALL_SUITS:
            for rank in range(MIN_RANK, MAX_RANK + 1):
                cards.append(Card(id=cid, suit=suit, rank=rank, deck_id=deck_id))
                cid += 1
    for _ in range(NUM_JOKERS):
        cards.append(Card(id=cid, is_joker=True))
        cid += 1
    rng.shuffle(cards)
    return cards
