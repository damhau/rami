"""The heuristic computer player."""

from __future__ import annotations

from conftest import C, D, H, S, card, two_player_state
from rami.game.ai import next_bot_intent
from rami.game.engine import apply
from rami.game.intents import Discard, DrawStock, LayMelds
from rami.game.state import Phase


def _no_meld_filler(n: int) -> list:
    # Distinct isolated cards that form neither a set nor a run.
    spec = [(S, 13), (H, 9), (D, 4), (C, 2), (D, 11), (S, 8), (H, 6), (C, 10), (S, 3)]
    return [card(s, r, 700 + i) for i, (s, r) in enumerate(spec[:n])]


def test_bot_draws_from_stock_on_its_turn():
    g = two_player_state(_no_meld_filler(9), _no_meld_filler(9), phase=Phase.AWAIT_DRAW, turn=0)
    assert next_bot_intent(g, 0) == DrawStock(0)


def test_bot_not_its_turn_does_nothing():
    g = two_player_state(_no_meld_filler(9), _no_meld_filler(9), phase=Phase.AWAIT_DRAW, turn=1)
    assert next_bot_intent(g, 0) is None


def test_bot_goes_out_when_contract_and_40_points_are_reachable():
    # Round 1 wants 1 brelan; three Aces (33) alone are < 40, so the bot must lay
    # a supplementary meld too. A A A + 5-6-7 of clubs = 33 + 18 = 51.
    hand = [
        card(S, 1, 1),
        card(H, 1, 2),
        card(D, 1, 3),
        card(C, 5, 4),
        card(C, 6, 5),
        card(C, 7, 6),
        *_no_meld_filler(7),
    ]
    g = two_player_state(hand, _no_meld_filler(9), round_no=1)  # phase await_discard
    intent = next_bot_intent(g, 0)
    assert isinstance(intent, LayMelds)
    g2, ev = apply(g, intent)
    assert g2.players[0].has_gone_out
    assert any(e.type == "went_out" for e in ev)


def test_bot_discards_when_it_cannot_go_out():
    g = two_player_state(_no_meld_filler(9), _no_meld_filler(9), round_no=1)  # await_discard
    intent = next_bot_intent(g, 0)
    assert isinstance(intent, Discard)


def test_bot_completes_a_full_turn_via_repeated_calls():
    # Drive the bot exactly as the transport does: apply moves until the turn passes.
    g = two_player_state(_no_meld_filler(9), _no_meld_filler(9), phase=Phase.AWAIT_DRAW, turn=0)
    g.stock = [card(H, 12, 500)]
    g.discard = []  # 2 players: no free-card offer
    for _ in range(10):
        intent = next_bot_intent(g, 0)
        if intent is None:
            break
        g, _ = apply(g, intent)
    assert g.turn_seat == 1  # the bot drew, then discarded, passing the turn
    assert g.phase == Phase.AWAIT_DRAW
