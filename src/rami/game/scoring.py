"""Round and game scoring."""

from __future__ import annotations

from .cards import Card, card_hand_value


def hand_score(hand: list[Card]) -> int:
    """Penalty points for the cards left in a hand at the end of a round."""
    return sum(card_hand_value(c) for c in hand)
