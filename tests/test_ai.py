"""The heuristic computer player."""

from __future__ import annotations

from conftest import C, D, H, S, card, joker, three_player_state, two_player_state
from rami.game.ai import _meld_points, next_bot_intent
from rami.game.cards import RANK_ACE_HIGH
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
    # A♠ A♥ + 5-6-7♣ (+ a spare 9♥ to discard); the A♦ on the discard completes
    # A-A-A (33) + run (18) = 51, leaving the 9♥ to discard (§3.10).
    hand = [
        card(S, 1, 1),
        card(H, 1, 2),
        card(C, 5, 3),
        card(C, 6, 4),
        card(C, 7, 5),
        card(H, 9, 6),
    ]
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
    # The engine keeps a run sent in a valid explicit order — Q-K-★ makes the
    # joker the Ace high (issue #2) — and canonicalizes any other order to the
    # lowest arrangement. The bot's valuation must agree in both cases, or it
    # will mis-judge go-outs (issue #17).
    ordered = [card(S, 12, 1), card(S, 13, 2), joker(3)]
    assert _meld_points(MeldKind.RUN, ordered) == cards_points(ordered, MeldKind.RUN) == 31
    shuffled = [joker(3), card(S, 13, 2), card(S, 12, 1)]  # not a valid order
    arranged = arrange_run(shuffled)
    assert arranged is not None
    assert _meld_points(MeldKind.RUN, shuffled) == cards_points(arranged, MeldKind.RUN) == 30


def test_bot_goes_out_by_placing_the_run_joker_at_the_high_end():
    # Issue #17: 3-3-3 (9 pts) + Q♣ K♣ ★. Valued with the joker low (J-Q-K) the
    # run is 30 and the total 39 — no go-out. Placed deliberately as Q-K-A it is
    # 31 and the total exactly 40, so the bot must order the run to go out.
    hand = [
        card(S, 3, 1),
        card(H, 3, 2),
        card(D, 3, 3),
        card(C, 12, 4),
        card(C, 13, 5),
        joker(6),
        card(H, 8, 7),  # spare kept back for the mandatory discard (§3.10)
    ]
    g = two_player_state(hand, _no_meld_filler(9), round_no=1)  # await_discard
    intent = next_bot_intent(g, 0)
    assert isinstance(intent, LayMelds)
    g2, _ = apply(g, intent)
    assert g2.players[0].has_gone_out
    run = next(m for m in g2.table_melds if m.kind == MeldKind.RUN)
    assert run.represents[6].rank == RANK_ACE_HIGH  # the joker is the Ace, not the Jack


def test_bot_prefers_the_higher_window_for_run_jokers():
    # Issue #17: 5-5-5 (15 pts) + K♣ ★ ★. Sent unordered, [K,★,★] canonicalizes
    # to J-Q-K (jokers worth 20); ordered as ★-K-★ (Q-K-A) they are worth 21 and
    # the high end stays recoverable. The bot must send the higher window.
    hand = [
        card(S, 5, 1),
        card(H, 5, 2),
        card(D, 5, 3),
        card(C, 13, 4),
        joker(5),
        joker(6),
        card(H, 2, 7),  # spare kept back for the mandatory discard (§3.10)
    ]
    g = two_player_state(hand, _no_meld_filler(9), round_no=1)  # await_discard
    intent = next_bot_intent(g, 0)
    assert isinstance(intent, LayMelds)
    g2, _ = apply(g, intent)
    assert g2.players[0].has_gone_out
    run = next(m for m in g2.table_melds if m.kind == MeldKind.RUN)
    assert sorted(r.rank for r in run.represents.values()) == [12, RANK_ACE_HIGH]


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


def test_bot_lays_off_a_placeable_card_instead_of_discarding():
    # Issue #1/#5: after going out, the bot must lay a placeable card onto a table
    # meld rather than discard it — especially when an opponent has a single card.
    from rami.game.intents import LayOff
    from rami.game.melds import Meld

    m = Meld(0, MeldKind.SET, [card(S, 9, 1), card(H, 9, 2), card(D, 9, 3)], 1)
    # Hand: 9♣ (lays off onto the 9s) + an isolated K♠ to discard afterwards.
    g = two_player_state(
        [card(C, 9, 10), card(S, 13, 11)], [card(D, 2, 20)], round_no=1, gone_out0=True
    )
    g.table_melds = [m]
    g.next_meld_id = 1
    assert len(g.players[1].hand) == 1  # opponent has one card
    intent = next_bot_intent(g, 0)
    assert intent == LayOff(0, 0, 10)  # lays off the 9♣, does not discard it
    g2, _ = apply(g, intent)
    # Now only the K♠ remains — it can't be laid off, so it is discarded.
    assert [c.id for c in g2.players[0].hand] == [11]
    assert isinstance(next_bot_intent(g2, 0), Discard)


def test_bot_lays_off_the_joker_and_discards_the_cheap_card():
    # Issue #14: with a set of 2s on the table (missing ♣) and [JOKER, 2♣] in
    # hand, both cards are placeable but one must be kept back for the mandatory
    # discard (§3.10). The joker (25 pts) must be laid off first so the forced
    # final discard is the cheap 2♣ — not the other way around.
    from rami.game.intents import LayOff
    from rami.game.melds import Meld

    m = Meld(0, MeldKind.SET, [card(S, 2, 1), card(H, 2, 2), card(D, 2, 3)], 1)
    g = two_player_state([joker(10), card(C, 2, 11)], [card(D, 9, 20)], round_no=1, gone_out0=True)
    g.table_melds = [m]
    g.next_meld_id = 1
    intent = next_bot_intent(g, 0)
    assert intent == LayOff(0, 0, 10)  # the joker, not the 2♣
    g2, _ = apply(g, intent)
    assert isinstance(next_bot_intent(g2, 0), Discard)  # only the 2♣ is left


def test_bot_does_not_take_a_discard_it_cannot_use():
    # Issue #16 (livelock): gone out with [A♠, A♥], the A♦ on the discard forms a
    # set — but laying it would use the whole hand, which §3.10 forbids, so the
    # bot would take it, fail to lay it, return it, and repeat forever. It must
    # draw from the stock instead and finish the turn normally.
    g = two_player_state(
        [card(S, 1, 1), card(H, 1, 2)],
        _no_meld_filler(5),
        round_no=1,
        phase=Phase.AWAIT_DRAW,
        turn=0,
        gone_out0=True,
    )
    g.discard = [card(D, 1, 50)]  # A♦: completes A-A-A but only by emptying the hand
    g.stock = [card(S, 7, 99), card(S, 8, 98)]
    assert next_bot_intent(g, 0) == DrawStock(0)
    # Drive the whole turn: it must pass to the opponent within a few moves.
    for _ in range(6):
        intent = next_bot_intent(g, 0)
        assert intent is not None
        g, _ = apply(g, intent)
        if g.turn_seat != 0:
            break
    assert g.turn_seat == 1


def test_bot_takes_the_discard_when_a_spare_remains():
    # Same shape plus a spare K♠: the ace set (3 cards) now leaves a card to
    # discard, so taking the A♦ is genuinely usable and still preferred.
    g = two_player_state(
        [card(S, 1, 1), card(H, 1, 2), card(S, 13, 3)],
        _no_meld_filler(5),
        round_no=1,
        phase=Phase.AWAIT_DRAW,
        turn=0,
        gone_out0=True,
    )
    g.discard = [card(D, 1, 50)]
    g.stock = [card(S, 7, 99)]
    assert next_bot_intent(g, 0) == DrawDiscard(0)


def test_bot_never_discards_a_layable_card_when_an_opponent_has_one_card():
    # Issue #18: seat 1 has gone out and holds a single card; the K♣ fits their
    # set of Ks on the table. Value-wise the K♣ is the natural shed (highest
    # junk), but discarding it hands the opponent the round — shed safe junk.
    from rami.game.melds import Meld

    m = Meld(0, MeldKind.SET, [card(S, 13, 1), card(H, 13, 2), card(D, 13, 3)], 1)
    hand = [card(C, 13, 10), card(H, 9, 11), card(D, 4, 12), card(C, 2, 13), card(S, 7, 14)]
    g = two_player_state(hand, [card(D, 5, 20)], round_no=1)  # await_discard
    g.players[1].has_gone_out = True
    g.table_melds = [m]
    g.next_meld_id = 1
    intent = next_bot_intent(g, 0)
    assert isinstance(intent, Discard)
    assert intent.card_id != 10  # never the layable K♣
    assert intent.card_id == 11  # the highest-value safe card (9♥)


def test_bot_prefers_a_safe_discard_over_a_layable_one_when_an_opponent_is_out():
    # Issue #18: same idea at a milder threat (opponent out with 3 cards) and a
    # run on the table — the Q♠ extends the 9-10-J♠ run, so shed the 9♥ instead.
    from rami.game.melds import Meld

    m = Meld(0, MeldKind.RUN, [card(S, 9, 1), card(S, 10, 2), card(S, 11, 3)], 1)
    hand = [card(S, 12, 10), card(H, 9, 11), card(D, 4, 12), card(C, 2, 13)]
    g = two_player_state(hand, [card(D, 5, 20), card(D, 8, 21), card(C, 11, 22)], round_no=1)
    g.players[1].has_gone_out = True
    g.table_melds = [m]
    g.next_meld_id = 1
    intent = next_bot_intent(g, 0)
    assert isinstance(intent, Discard)
    assert intent.card_id != 10  # never the layable Q♠
    assert intent.card_id == 11  # the highest-value safe card (9♥)


def test_bot_dumps_points_over_structure_when_an_opponent_is_about_to_win():
    # Issue #18: seat 1 is out with one card, so the round can end any moment.
    # Normally the lone 2♦ is the discard (9-10♠ is a near-run worth keeping),
    # but with every held point about to count, the bot sheds the 10♠ instead.
    hand = [card(S, 10, 10), card(S, 9, 11), card(D, 2, 12)]
    g = two_player_state(hand, [card(D, 5, 20)], round_no=1)  # await_discard
    g.players[1].has_gone_out = True
    intent = next_bot_intent(g, 0)
    assert isinstance(intent, Discard)
    assert intent.card_id == 10  # the 10♠, not the cheap lone 2♦


def test_bot_discard_choice_is_unchanged_while_nobody_is_out():
    # Issue #18 must not alter pre-threat behaviour: with no opponent out, the
    # same hand keeps the near-run and sheds the lone junk card.
    hand = [card(S, 10, 10), card(S, 9, 11), card(D, 2, 12)]
    g = two_player_state(hand, [card(D, 5, 20)], round_no=1)  # await_discard
    intent = next_bot_intent(g, 0)
    assert isinstance(intent, Discard)
    assert intent.card_id == 12  # the lone 2♦


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
