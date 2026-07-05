"""Shared test builders."""

from __future__ import annotations

from rami.game.cards import Card, Suit
from rami.game.state import GameState, Phase, PlayerState

S, H, D, C = Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS

_next = [10_000]


def card(suit: Suit, rank: int, cid: int | None = None) -> Card:
    if cid is None:
        _next[0] += 1
        cid = _next[0]
    return Card(id=cid, suit=suit, rank=rank)


def joker(cid: int | None = None) -> Card:
    if cid is None:
        _next[0] += 1
        cid = _next[0]
    return Card(id=cid, is_joker=True)


def two_player_state(
    hand0: list[Card],
    hand1: list[Card] | None = None,
    *,
    round_no: int = 1,
    phase: Phase = Phase.AWAIT_DISCARD,
    turn: int = 0,
    gone_out0: bool = False,
) -> GameState:
    p0 = PlayerState(seat=0, name="A", hand=list(hand0), has_gone_out=gone_out0)
    p1 = PlayerState(seat=1, name="B", hand=list(hand1 or []))
    return GameState(
        players=[p0, p1],
        phase=phase,
        round_no=round_no,
        turn_seat=turn,
        dealer_seat=(turn - 1) % 2,
    )
