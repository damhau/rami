"""Cards, deck, meld validation, joker representation, points, lay-off."""

from __future__ import annotations

import random

from conftest import C, D, H, S, card, joker
from rami.game.cards import NUM_JOKERS, build_deck, card_hand_value
from rami.game.melds import (
    Meld,
    MeldKind,
    cards_points,
    is_valid_run,
    is_valid_set,
    meld_points,
    repr_matches_card,
    try_lay_off,
)


def test_deck_is_110_cards_with_6_jokers():
    deck = build_deck(random.Random(1))
    assert len(deck) == 110
    assert sum(1 for c in deck if c.is_joker) == NUM_JOKERS
    assert sum(1 for c in deck if not c.is_joker) == 104


def test_card_hand_values():
    assert card_hand_value(card(S, 1)) == 11  # Ace
    assert card_hand_value(card(S, 13)) == 10  # King
    assert card_hand_value(card(S, 11)) == 10  # Jack
    assert card_hand_value(card(S, 7)) == 7
    assert card_hand_value(joker()) == 25


def test_set_validity():
    assert is_valid_set([card(S, 7), card(H, 7), card(D, 7)])
    assert not is_valid_set([card(S, 7), card(H, 8), card(D, 7)])  # mixed rank
    assert not is_valid_set([card(S, 7), card(H, 7)])  # too short
    assert not is_valid_set([card(S, 7), card(S, 7), card(S, 7)])  # 3x one suit


def test_set_duplicate_suit_requires_all_suits_present():
    # A 2nd-deck copy of a suit is only legal once all four suits are present
    # (DESIGN.md §3.9). A bare triplet with a duplicate suit is invalid.
    assert not is_valid_set([card(S, 8), card(S, 8), card(H, 8)])
    # Once all four suits are down, a second-deck copy is fine.
    assert is_valid_set(
        [card(S, 7), card(H, 7), card(D, 7), card(C, 7), card(S, 7)]
    )
    # A joker can stand in for a missing suit, unlocking the double.
    assert is_valid_set(
        [card(S, 6), card(S, 6), card(H, 6), card(D, 6), joker()]
    )
    # ...but not when suits are still missing (joker only covers one).
    assert not is_valid_set([card(S, 8), card(S, 8), card(H, 8), joker()])


def test_run_validity_and_ace_rules():
    assert is_valid_run([card(S, 4), card(S, 5), card(S, 6)])
    assert not is_valid_run([card(S, 4), card(H, 5), card(S, 6)])  # mixed suit
    # Ace low and high, no wrap.
    assert is_valid_run([card(C, 1), card(C, 2), card(C, 3)])  # A-2-3
    assert is_valid_run([card(H, 12), card(H, 13), card(H, 1)])  # Q-K-A
    assert not is_valid_run([card(C, 13), card(C, 1), card(C, 2)])  # K-A-2 wrap


def test_run_validity_is_order_independent():
    # Cards may arrive in any order (e.g. UI click order).
    assert is_valid_run([card(C, 13), card(C, 11), card(C, 12)])  # K J Q -> J Q K
    assert is_valid_run([card(S, 6), card(S, 4), card(S, 5)])
    assert not is_valid_run([card(S, 6), card(S, 4), card(S, 4)])  # dup rank


def test_arrange_run_orders_cards():
    from rami.game.melds import arrange_run

    seq = arrange_run([card(C, 13, 1), card(C, 11, 2), card(C, 12, 3)])
    assert seq is not None
    assert [c.rank for c in seq] == [11, 12, 13]
    # Joker slotted into the gap even when passed out of order.
    seq = arrange_run([card(S, 6, 4), card(S, 4, 5), joker(6)])
    assert seq is not None
    assert [c.id for c in seq] == [5, 6, 4]  # 4S, joker(=5S), 6S
    assert arrange_run([card(S, 4), card(H, 5), card(S, 6)]) is None  # mixed suit


def test_run_with_joker_filling_gap():
    # 4S _ 6S with a joker as 5S
    cards = [card(S, 4), joker(), card(S, 6)]
    assert is_valid_run(cards)
    m = Meld(0, MeldKind.RUN, cards, 0)
    (rep,) = m.represents.values()
    assert rep.suit == S
    assert rep.rank == 5


def test_joker_set_representation_targets_missing_suit():
    cards = [card(S, 7), card(H, 7), card(D, 7), joker(99)]
    m = Meld(0, MeldKind.SET, cards, 0)
    assert m.represents[99].suit == C
    assert m.represents[99].rank == 7


def test_meld_points_counts_joker_as_represented_card():
    # K K K + joker(=4th King) -> 10*4 = 40
    cards = [card(H, 13), card(D, 13), card(C, 13), joker()]
    assert cards_points(cards, MeldKind.SET) == 40
    # A run 4-5-6 with joker as 7 -> 4+5+6+7 = 22
    run = [card(S, 4), card(S, 5), card(S, 6), joker()]
    assert cards_points(run, MeldKind.RUN) == 22


def test_repr_matches_high_ace():
    cards = [card(H, 12), card(H, 13), joker(7)]  # Q-K-? -> joker is high Ace
    m = Meld(0, MeldKind.RUN, cards, 0)
    rep = m.represents[7]
    assert rep.rank == 14
    assert repr_matches_card(rep, card(H, 1))  # physical Ace of hearts matches
    assert not repr_matches_card(rep, card(S, 1))


def test_lay_off_set_and_run():
    set_meld = Meld(0, MeldKind.SET, [card(S, 9), card(H, 9), card(D, 9)], 0)
    assert try_lay_off(set_meld, card(C, 9)) is not None
    assert try_lay_off(set_meld, card(C, 8)) is None

    run_meld = Meld(1, MeldKind.RUN, [card(S, 4), card(S, 5), card(S, 6)], 0)
    assert try_lay_off(run_meld, card(S, 7)) is not None  # append
    assert try_lay_off(run_meld, card(S, 3)) is not None  # prepend
    assert try_lay_off(run_meld, card(S, 9)) is None


def test_meld_points_on_committed_meld():
    m = Meld(0, MeldKind.SET, [card(S, 5), card(H, 5), card(D, 5)], 0)
    assert meld_points(m) == 15
