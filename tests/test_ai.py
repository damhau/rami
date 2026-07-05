"""The heuristic computer player."""

from __future__ import annotations

from conftest import C, D, H, S, card, joker, three_player_state, two_player_state
from rami.game.ai import _meld_points, next_bot_intent
from rami.game.engine import apply, new_game, start_round
from rami.game.intents import ClaimFreeCard, Discard, DrawDiscard, DrawStock, LayMelds
from rami.game.melds import MeldKind, arrange_run, cards_points
from rami.game.state import FreeCardOffer, Phase


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


def test_bot_keeps_a_pair_and_discards_the_isolated_high_card():
    # 7♠ 7♥ is a pair (worth keeping toward a set); K♦ is isolated dead weight.
    hand = [card(S, 7, 1), card(H, 7, 2), card(D, 13, 3), card(C, 2, 4), card(D, 4, 5)]
    g = two_player_state(hand, _no_meld_filler(5), round_no=1)  # await_discard
    intent = next_bot_intent(g, 0)
    assert isinstance(intent, Discard)
    assert intent.card_id == 3  # the K♦, not one of the paired 7s


def test_bot_takes_the_discard_to_go_out():
    # A♠ A♥ + 5-6-7♣; the A♦ on the discard completes A-A-A (33) + run (18) = 51.
    hand = [card(S, 1, 1), card(H, 1, 2), card(C, 5, 3), card(C, 6, 4), card(C, 7, 5)]
    g = two_player_state(hand, _no_meld_filler(5), round_no=1, phase=Phase.AWAIT_DRAW, turn=0)
    g.discard = [card(D, 1, 50)]  # A♦ face-up
    g.stock = [card(S, 2, 99)]
    assert next_bot_intent(g, 0) == DrawDiscard(0)


def test_bot_passes_a_useless_discard():
    hand = [card(S, 7, 1), card(H, 2, 2), card(C, 9, 3), card(D, 4, 4), card(S, 11, 5)]
    g = two_player_state(hand, _no_meld_filler(5), round_no=1, phase=Phase.AWAIT_DRAW, turn=0)
    g.discard = [card(D, 8, 50)]  # doesn't help
    g.stock = [card(S, 2, 99)]
    assert next_bot_intent(g, 0) == DrawStock(0)


def test_bot_claims_a_free_card_that_completes_a_meld():
    hands = [_no_meld_filler(5), [card(S, 7, 1), card(H, 7, 2)], _no_meld_filler(5)]
    g = three_player_state(hands, round_no=1, turn=0, phase=Phase.AWAIT_DISCARD)
    g.discard = [card(D, 7, 50)]  # 7♦ completes 7♠ 7♥ 7♦
    g.free_card = FreeCardOffer(pending_seats=[1], resume_seat=0)
    assert next_bot_intent(g, 1) == ClaimFreeCard(1)


def test_bot_scores_runs_like_the_engine():
    # A joker in Q-K-? is valued by the engine as the Jack (cheapest arrangement),
    # not the Ace. The bot must agree, or it will try an illegal go-out.
    cards = [card(S, 12, 1), card(S, 13, 2), joker(3)]
    arranged = arrange_run(cards)
    assert arranged is not None
    assert _meld_points(MeldKind.RUN, cards) == cards_points(arranged, MeldKind.RUN) == 30


def test_bot_never_produces_an_illegal_move_across_many_deals():
    # Regression for the ContractNotMet crash: drive all-bot rounds over many
    # deals; applying a bot move must never raise.
    for seed in range(80):
        g = new_game(["A", "B", "C"], rng_seed=seed)
        g, _ = start_round(g)
        for _ in range(500):
            if g.phase in (Phase.ROUND_OVER, Phase.GAME_OVER):
                break
            offer = g.free_card
            seat = offer.pending_seats[0] if offer and offer.pending_seats else g.turn_seat
            intent = next_bot_intent(g, seat)
            assert intent is not None, (seed, g.phase)
            g, _ = apply(g, intent)  # must not raise


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
