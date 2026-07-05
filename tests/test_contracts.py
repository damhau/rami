"""Contract definitions and satisfaction."""

from __future__ import annotations

from rami.game.contracts import (
    CONTRACTS,
    TOTAL_ROUNDS,
    LaidMeld,
    contract_for,
    satisfies_contract,
)
from rami.game.melds import MeldKind

SET, RUN = MeldKind.SET, MeldKind.RUN


def test_there_are_11_contracts():
    assert TOTAL_ROUNDS == 11
    assert set(CONTRACTS) == set(range(1, 12))


def test_round1_single_triplet():
    c = contract_for(1)
    assert satisfies_contract(c, [LaidMeld(SET, 3)])
    assert not satisfies_contract(c, [LaidMeld(RUN, 3)])


def test_round3_run_of_five_needs_length():
    c = contract_for(3)
    assert not satisfies_contract(c, [LaidMeld(RUN, 4)])
    assert satisfies_contract(c, [LaidMeld(RUN, 5)])
    assert satisfies_contract(c, [LaidMeld(RUN, 7)])


def test_round5_run4_plus_triplet():
    c = contract_for(5)
    assert satisfies_contract(c, [LaidMeld(RUN, 4), LaidMeld(SET, 3)])
    assert not satisfies_contract(c, [LaidMeld(RUN, 4), LaidMeld(RUN, 4)])
    assert not satisfies_contract(c, [LaidMeld(RUN, 3), LaidMeld(SET, 3)])  # run too short


def test_round11_three_triplets_plus_run():
    c = contract_for(11)
    assert satisfies_contract(
        c, [LaidMeld(SET, 3), LaidMeld(SET, 4), LaidMeld(SET, 3), LaidMeld(RUN, 4)]
    )
    # missing the run
    assert not satisfies_contract(c, [LaidMeld(SET, 3), LaidMeld(SET, 3), LaidMeld(SET, 3)])


def test_extra_melds_are_allowed():
    c = contract_for(1)  # one triplet
    assert satisfies_contract(c, [LaidMeld(SET, 3), LaidMeld(RUN, 5), LaidMeld(SET, 3)])


def test_longer_meld_can_satisfy_two_short_requirements_correctly():
    # round 6 = two runs of 4; a single long run cannot cover both.
    c = contract_for(6)
    assert not satisfies_contract(c, [LaidMeld(RUN, 8)])
    assert satisfies_contract(c, [LaidMeld(RUN, 4), LaidMeld(RUN, 5)])
