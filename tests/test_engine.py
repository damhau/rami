"""Engine: turn flow, free-card chain, go-out rules, jokers, scoring."""

from __future__ import annotations

import pytest

from conftest import C, D, H, S, card, joker, three_player_state, two_player_state
from rami.core.exceptions import ContractNotMet, IllegalMove, NotYourTurn
from rami.game import engine
from rami.game.engine import apply, new_game, start_round
from rami.game.intents import (
    ClaimFreeCard,
    Discard,
    DrawDiscard,
    DrawStock,
    LayMelds,
    LayOff,
    MeldSpec,
    PassFreeCard,
    RecoverJoker,
    ReturnDiscard,
)
from rami.game.melds import Meld, MeldKind
from rami.game.state import Phase

SET, RUN = MeldKind.SET, MeldKind.RUN


def _filler(n: int) -> list:
    # Assorted cards that don't form melds among themselves.
    suits = [D, H, C, S]
    return [card(suits[i % 4], 2 + (i % 5), 900 + i) for i in range(n)]


# --------------------------------------------------------------------------- #
# Setup / dealing
# --------------------------------------------------------------------------- #


def test_start_round_deals_13_each_and_flips_discard():
    g = new_game(["A", "B", "C"], rng_seed=7)
    g, ev = start_round(g)
    assert g.phase == Phase.AWAIT_DRAW
    assert all(len(p.hand) == 13 for p in g.players)
    assert len(g.discard) == 1
    assert len(g.stock) == 110 - 13 * 3 - 1
    assert g.turn_seat == (g.dealer_seat + 1) % 3
    assert any(e.type == "round_started" for e in ev)


def test_opening_dealer_is_randomized():
    # Different seeds should not always start the same seat (the old code always
    # made seat 0 the dealer, so seat 1 always began).
    dealers = set()
    for seed in range(12):
        g = new_game(["A", "B", "C"], rng_seed=seed)
        g, _ = start_round(g)
        assert g.turn_seat == (g.dealer_seat + 1) % 3
        dealers.add(g.dealer_seat)
    assert len(dealers) > 1


def test_apply_does_not_mutate_input_state():
    g = two_player_state(_filler(13), _filler(13), phase=Phase.AWAIT_DRAW)
    g.stock = [card(S, 2, 1)]
    g.discard = [card(H, 9, 2)]
    before = len(g.players[0].hand)
    apply(g, DrawStock(0))
    assert len(g.players[0].hand) == before  # original untouched


# --------------------------------------------------------------------------- #
# Turn flow
# --------------------------------------------------------------------------- #


def test_not_your_turn_is_rejected():
    g = two_player_state(_filler(13), _filler(13), phase=Phase.AWAIT_DRAW, turn=0)
    g.stock = [card(S, 2, 1)]
    with pytest.raises(NotYourTurn):
        apply(g, DrawStock(1))


def test_basic_draw_then_discard_advances_turn():
    g = two_player_state(_filler(13), _filler(13), phase=Phase.AWAIT_DRAW, turn=0)
    g.stock = [card(S, 2, 1)]
    g.discard = []  # no free-card offer
    g, _ = apply(g, DrawStock(0))
    assert g.phase == Phase.AWAIT_DISCARD
    assert len(g.players[0].hand) == 14
    g, _ = apply(g, Discard(0, 1))
    assert g.phase == Phase.AWAIT_DRAW
    assert g.turn_seat == 1
    assert g.discard[-1].id == 1


def test_stock_reshuffles_from_discard_when_empty():
    g = two_player_state(_filler(13), _filler(13), phase=Phase.AWAIT_DRAW, turn=0)
    g.stock = []
    g.discard = [card(S, 2, 1), card(S, 3, 2), card(S, 4, 3), card(H, 9, 4)]
    g, _ = apply(g, DrawStock(0))
    assert len(g.players[0].hand) == 14
    assert len(g.discard) == 1  # only the kept top remains


# --------------------------------------------------------------------------- #
# Free-card chain
# --------------------------------------------------------------------------- #


def test_two_players_get_no_free_card_offer():
    # With only 2 players the free-card chain does not apply (§3.7): drawing from
    # stock goes straight to the discard step.
    g = two_player_state(_filler(13), _filler(13), phase=Phase.AWAIT_DRAW, turn=0)
    g.stock = [card(S, 2, 1)]
    g.discard = [card(H, 9, 2)]
    g, _ = apply(g, DrawStock(0))
    assert g.phase == Phase.AWAIT_DISCARD
    assert g.free_card is None


def test_free_card_offered_without_blocking_drawer():
    g = three_player_state([_filler(13), _filler(13), _filler(13)], phase=Phase.AWAIT_DRAW, turn=0)
    g.stock = [card(S, 2, 1)]
    g.discard = [card(H, 9, 2)]
    g, _ = apply(g, DrawStock(0))
    # The drawer proceeds to discard; the offer is open to the following seats.
    assert g.phase == Phase.AWAIT_DISCARD
    assert g.free_card is not None
    assert g.free_card.pending_seats == [1, 2]


def test_free_card_claimed_out_of_turn():
    g = three_player_state([_filler(13), _filler(13), _filler(13)], phase=Phase.AWAIT_DRAW, turn=0)
    g.stock = [card(S, 2, 1)]
    g.discard = [card(H, 9, 2)]
    g, _ = apply(g, DrawStock(0))
    g, _ = apply(g, ClaimFreeCard(1))  # seat 1 claims although it is seat 0's turn
    assert any(c.id == 2 for c in g.players[1].hand)
    assert g.discard == []
    assert g.free_card is None
    assert g.phase == Phase.AWAIT_DISCARD  # still the drawer's turn


def test_free_card_passes_advance_then_expire():
    g = three_player_state([_filler(13), _filler(13), _filler(13)], phase=Phase.AWAIT_DRAW, turn=0)
    g.stock = [card(S, 2, 1)]
    g.discard = [card(H, 9, 2)]
    g, _ = apply(g, DrawStock(0))
    g, _ = apply(g, PassFreeCard(1))
    assert g.free_card is not None
    assert g.free_card.pending_seats == [2]
    g, _ = apply(g, PassFreeCard(2))
    assert g.free_card is None
    assert g.discard[-1].id == 2  # nobody claimed — the card stays on the pile


def test_free_card_offer_closes_when_drawer_discards():
    g = three_player_state([_filler(13), _filler(13), _filler(13)], phase=Phase.AWAIT_DRAW, turn=0)
    g.stock = [card(S, 2, 1)]
    g.discard = [card(H, 9, 2)]
    g, _ = apply(g, DrawStock(0))
    assert g.free_card is not None
    g, _ = apply(g, Discard(0, 900))  # drawer ends the turn
    assert g.free_card is None
    with pytest.raises(IllegalMove):
        apply(g, ClaimFreeCard(1))  # window is closed


def test_wrong_seat_cannot_decide_free_card():
    g = three_player_state([_filler(13), _filler(13), _filler(13)], phase=Phase.AWAIT_DRAW, turn=0)
    g.stock = [card(S, 2, 1)]
    g.discard = [card(H, 9, 2)]
    g, _ = apply(g, DrawStock(0))
    with pytest.raises(IllegalMove):
        apply(g, ClaimFreeCard(2))  # seat 2 must wait behind seat 1


# --------------------------------------------------------------------------- #
# Drawing from the discard obliges laying that card
# --------------------------------------------------------------------------- #


def test_draw_discard_sets_obligation_and_blocks_plain_discard():
    g = two_player_state([*_filler(12)], _filler(13), phase=Phase.AWAIT_DRAW, turn=0)
    g.discard = [card(H, 9, 50)]
    g.stock = [card(S, 2, 1)]
    g, _ = apply(g, DrawDiscard(0))
    assert g.taken_from_discard_id == 50
    assert g.phase == Phase.AWAIT_DISCARD
    with pytest.raises(IllegalMove):
        apply(g, Discard(0, 900))  # cannot discard before laying the taken card


def test_return_discard_undoes_the_pickup():
    # Escape hatch for the soft-lock: if the taken card can't be used, put it back.
    g = two_player_state([*_filler(12)], _filler(13), phase=Phase.AWAIT_DRAW, turn=0)
    g.discard = [card(S, 4, 40), card(H, 9, 50)]  # 50 is the face-up top
    g.stock = [card(S, 2, 1)]
    g, _ = apply(g, DrawDiscard(0))
    assert g.taken_from_discard_id == 50
    assert len(g.players[0].hand) == 13

    g, ev = apply(g, ReturnDiscard(0))
    assert g.taken_from_discard_id is None
    assert g.phase == Phase.AWAIT_DRAW  # back to the draw step
    assert g.discard[-1].id == 50  # card is back on top of the discard
    assert len(g.players[0].hand) == 12
    assert not any(c.id == 50 for c in g.players[0].hand)
    assert any(e.type == "returned_discard" for e in ev)


def test_return_discard_rejected_when_nothing_taken():
    g = two_player_state(_filler(13), _filler(13), phase=Phase.AWAIT_DISCARD, turn=0)
    with pytest.raises(IllegalMove):
        apply(g, ReturnDiscard(0))


# --------------------------------------------------------------------------- #
# Going out: contract + 40 points
# --------------------------------------------------------------------------- #


def test_go_out_with_four_kings_round1():
    hand = [card(S, 13, 1), card(H, 13, 2), card(D, 13, 3), card(C, 13, 4), *_filler(9)]
    g = two_player_state(hand, _filler(13), round_no=1)
    g, ev = apply(g, LayMelds(0, [MeldSpec(SET, [1, 2, 3, 4])]))
    assert g.players[0].has_gone_out
    assert len(g.table_melds) == 1
    assert len(g.players[0].hand) == 9
    assert any(e.type == "went_out" for e in ev)


def test_go_out_rejected_below_40_points():
    hand = [card(S, 7, 1), card(H, 7, 2), card(D, 7, 3), *_filler(10)]
    g = two_player_state(hand, _filler(13), round_no=1)
    with pytest.raises(ContractNotMet):
        apply(g, LayMelds(0, [MeldSpec(SET, [1, 2, 3])]))  # only 21 points


def test_go_out_rejected_when_contract_kind_wrong():
    # Round 2 wants a run of 4; a set does not satisfy it.
    hand = [card(S, 13, 1), card(H, 13, 2), card(D, 13, 3), card(C, 13, 4), *_filler(9)]
    g = two_player_state(hand, _filler(13), round_no=2)
    with pytest.raises(ContractNotMet):
        apply(g, LayMelds(0, [MeldSpec(SET, [1, 2, 3, 4])]))


def test_go_out_with_unordered_run_of_four_round2():
    # Round 2 wants a run of 4; the client may send the ids in click order.
    # 10-J-Q-K of spades = 40 points, passed out of order.
    hand = [card(S, 13, 1), card(S, 11, 2), card(S, 10, 3), card(S, 12, 4), *_filler(9)]
    g = two_player_state(hand, _filler(13), round_no=2)
    g, _ = apply(g, LayMelds(0, [MeldSpec(RUN, [1, 2, 3, 4])]))
    assert g.players[0].has_gone_out
    assert [c.rank for c in g.table_melds[0].cards] == [10, 11, 12, 13]


def test_go_out_with_joker_counts_represented_value():
    # K K K + joker(=4th King) -> 40 points, satisfies round 1.
    hand = [card(H, 13, 1), card(D, 13, 2), card(C, 13, 3), joker(4), *_filler(9)]
    g = two_player_state(hand, _filler(13), round_no=1)
    g, _ = apply(g, LayMelds(0, [MeldSpec(SET, [1, 2, 3, 4])]))
    assert g.players[0].has_gone_out


def test_go_out_must_use_card_taken_from_discard():
    hand = [card(H, 13, 1), card(D, 13, 2), card(C, 13, 3), joker(4), *_filler(9)]
    g = two_player_state(hand, _filler(13), round_no=1, phase=Phase.AWAIT_DRAW)
    g.discard = [card(S, 13, 50)]  # King of spades on the discard
    g.stock = [card(S, 2, 99)]
    g, _ = apply(g, DrawDiscard(0))  # take the King, must use it
    # Going out without the taken card is rejected.
    with pytest.raises(IllegalMove):
        apply(g, LayMelds(0, [MeldSpec(SET, [1, 2, 3, 4])]))
    # Using it (KS + KH + KD + KC = 40) is fine.
    g2, _ = apply(g, LayMelds(0, [MeldSpec(SET, [50, 1, 2, 3])]))
    assert g2.players[0].has_gone_out
    assert g2.taken_from_discard_id is None


# --------------------------------------------------------------------------- #
# Lay off / joker recovery (only after going out)
# --------------------------------------------------------------------------- #


def test_lay_off_requires_having_gone_out():
    m = Meld(0, SET, [card(S, 9, 1), card(H, 9, 2), card(D, 9, 3)], 0)
    g = two_player_state([card(C, 9, 5), card(S, 2, 6)], round_no=1, gone_out0=False)
    g.table_melds = [m]
    g.next_meld_id = 1
    with pytest.raises(IllegalMove):
        apply(g, LayOff(0, 0, 5))


def test_lay_off_extends_meld_after_going_out():
    m = Meld(0, SET, [card(S, 9, 1), card(H, 9, 2), card(D, 9, 3)], 0)
    g = two_player_state([card(C, 9, 5), card(S, 2, 6)], round_no=1, gone_out0=True)
    g.table_melds = [m]
    g.next_meld_id = 1
    g, _ = apply(g, LayOff(0, 0, 5))
    assert len(g.table_melds[0].cards) == 4
    assert not any(c.id == 5 for c in g.players[0].hand)


def test_recover_joker_swaps_real_card_for_joker():
    m = Meld(0, SET, [card(S, 7, 1), card(H, 7, 2), card(D, 7, 3), joker(4)], 0)
    assert m.represents[4].suit == C  # joker stands in for 7C
    g = two_player_state([card(C, 7, 5), card(S, 2, 6)], round_no=1, gone_out0=True)
    g.table_melds = [m]
    g.next_meld_id = 1
    g, _ = apply(g, RecoverJoker(0, 0, 5))
    assert any(c.id == 4 and c.is_joker for c in g.players[0].hand)  # joker recovered
    assert any(c.id == 5 for c in g.table_melds[0].cards)  # real 7C now in meld
    assert not any(c.is_joker for c in g.table_melds[0].cards)


def test_lay_off_matching_card_recovers_joker():
    # Laying the exact represented card onto a meld (a lay-off action) recovers
    # the joker rather than extending the meld (DESIGN.md §3.9).
    m = Meld(0, SET, [card(S, 7, 1), card(H, 7, 2), card(D, 7, 3), joker(4)], 0)
    assert m.represents[4].suit == C  # joker stands in for 7C
    g = two_player_state([card(C, 7, 5), card(S, 2, 6)], round_no=1, gone_out0=True)
    g.table_melds = [m]
    g.next_meld_id = 1
    g, ev = apply(g, LayOff(0, 0, 5))
    assert any(c.id == 4 and c.is_joker for c in g.players[0].hand)  # joker recovered
    assert not any(c.is_joker for c in g.table_melds[0].cards)
    assert len(g.table_melds[0].cards) == 4  # meld did not grow — the 7C took the slot
    assert any(e.type == "recovered_joker" for e in ev)


def test_recover_joker_with_card_taken_from_discard_clears_obligation():
    # Regression: drawing the face-up card and using it to recover a joker must
    # discharge the discard-pickup obligation, so the turn can finish on a
    # discard (previously this soft-locked the turn).
    m = Meld(0, SET, [card(S, 7, 1), card(H, 7, 2), card(D, 7, 3), joker(4)], 0)
    assert m.represents[4].suit == C  # joker stands in for 7C
    g = two_player_state(
        [card(S, 2, 6)], [card(H, 5, 7)], round_no=1, phase=Phase.AWAIT_DRAW, gone_out0=True
    )
    g.discard = [card(C, 7, 5)]  # the real 7C is face-up on the discard
    g.table_melds = [m]
    g.next_meld_id = 1

    g, _ = apply(g, DrawDiscard(0))
    assert g.taken_from_discard_id == 5
    g, _ = apply(g, RecoverJoker(0, 0, 5))
    assert g.taken_from_discard_id is None  # obligation discharged by the recovery
    assert any(c.id == 4 and c.is_joker for c in g.players[0].hand)  # joker in hand

    # The turn can now end normally on a discard — no soft-lock.
    g, _ = apply(g, Discard(0, 6))
    assert g.phase == Phase.AWAIT_DRAW
    assert g.turn_seat == 1


# --------------------------------------------------------------------------- #
# Round / game end & scoring
# --------------------------------------------------------------------------- #


def test_round_ends_and_scores_when_last_card_discarded():
    g = two_player_state(
        [card(S, 5, 1)],
        [card(H, 13, 2), card(D, 1, 3)],  # King(10) + Ace(11) = 21
        round_no=1,
        gone_out0=True,
    )
    g, ev = apply(g, Discard(0, 1))
    assert g.phase == Phase.ROUND_OVER
    assert g.players[0].round_score == 0
    assert g.players[1].round_score == 21
    assert g.players[1].total_score == 21
    assert any(e.type == "round_over" for e in ev)


def test_cannot_lay_off_your_last_card():
    # §3.10: a turn always ends on a discard — laying off the last card (which
    # would empty the hand without a discard) is rejected.
    m = Meld(0, SET, [card(S, 9, 1), card(H, 9, 2), card(D, 9, 3)], 0)
    g = two_player_state([card(C, 9, 5)], [card(H, 13, 7)], round_no=1, gone_out0=True)
    g.table_melds = [m]
    g.next_meld_id = 1
    with pytest.raises(IllegalMove):
        apply(g, LayOff(0, 0, 5))
    # The round is not over; the player still holds the card to discard.
    assert g.phase == Phase.AWAIT_DISCARD
    assert len(g.players[0].hand) == 1


def test_cannot_lay_your_whole_hand_to_go_out():
    # A go-out that would leave nothing to discard is rejected (§3.10): the four
    # Kings are exactly the hand, so laying them all leaves no discard.
    hand = [card(S, 13, 1), card(H, 13, 2), card(D, 13, 3), card(C, 13, 4)]
    g = two_player_state(hand, _filler(13), round_no=1)
    with pytest.raises(IllegalMove):
        apply(g, LayMelds(0, [MeldSpec(SET, [1, 2, 3, 4])]))
    assert not g.players[0].has_gone_out


def test_go_out_keeping_one_card_then_discard_ends_round():
    # Four Kings + one spare: go out (keep the spare), then discard it to win.
    hand = [card(S, 13, 1), card(H, 13, 2), card(D, 13, 3), card(C, 13, 4), card(S, 2, 5)]
    g = two_player_state(hand, [card(H, 9, 7)], round_no=1)
    g, _ = apply(g, LayMelds(0, [MeldSpec(SET, [1, 2, 3, 4])]))
    assert g.players[0].has_gone_out
    assert g.phase == Phase.AWAIT_DISCARD
    assert [c.id for c in g.players[0].hand] == [5]
    g, ev = apply(g, Discard(0, 5))
    assert g.phase == Phase.ROUND_OVER
    assert g.players[0].round_score == 0
    assert any(e.type == "round_over" for e in ev)


def test_game_over_after_round_11():
    g = two_player_state([card(S, 5, 1)], [card(H, 13, 2)], round_no=11, gone_out0=True)
    g, ev = apply(g, Discard(0, 1))
    assert g.phase == Phase.GAME_OVER
    assert any(e.type == "game_over" for e in ev)


def test_go_out_const_is_40():
    assert engine.GO_OUT_MIN_POINTS == 40
