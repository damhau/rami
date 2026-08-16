"""Property test for the free-card window (§3.7, issues #26 / #38 / #39).

Randomized play — including the discard pickups and put-backs the heuristic bot
avoids — checked against an independent model of which card is claimable:

* a discard (or the round-start flip) makes that card the *live* one;
* refusing it (a stock draw) settles it, and so does genuinely taking it;
* taking it and putting it back leaves it live — the pickup never happened.

The engine must offer exactly the live card, never an older one that newer
discards were piled onto (#38), and never skip a live one (#39).
"""

from __future__ import annotations

import random

import pytest

from rami.core.exceptions import AppError
from rami.game import ai
from rami.game.engine import apply, new_game, start_round
from rami.game.intents import (
    ClaimFreeCard,
    Discard,
    DrawDiscard,
    DrawStock,
    Intent,
    PassFreeCard,
    ReturnDiscard,
)
from rami.game.state import GameState, Phase

MAX_STEPS = 4000


def _random_intent(state: GameState, rng: random.Random) -> tuple[int, Intent | None]:
    """A legal-ish move, biased towards the paths the bot policy never explores."""
    offer = state.free_card
    if offer is not None and offer.pending_seats:
        seat = offer.pending_seats[0]
        if rng.random() < 0.5:
            return seat, ClaimFreeCard(seat)
        return seat, ai.next_bot_intent(state, seat) or PassFreeCard(seat)

    seat = state.turn_seat
    if state.phase == Phase.AWAIT_DRAW and state.discard and rng.random() < 0.35:
        return seat, DrawDiscard(seat)
    if (
        state.phase == Phase.AWAIT_DISCARD
        and state.taken_from_discard_id is not None
        and rng.random() < 0.5
    ):
        return seat, ReturnDiscard(seat)
    return seat, ai.next_bot_intent(state, seat)


def _play(num_players: int, seed: int, rounds: int = 2) -> None:
    rng = random.Random(seed)
    state = new_game([f"P{i}" for i in range(num_players)], rng_seed=seed)
    state, _ = start_round(state)
    live: int | None = state.discard[-1].id  # the claimable card, per the model
    held: int | None = None  # what a pickup took out of the live slot

    for _ in range(MAX_STEPS):
        if state.phase == Phase.GAME_OVER:
            return
        if state.phase == Phase.ROUND_OVER:
            if state.round_no >= rounds:
                return
            state, _ = start_round(state)
            live, held = state.discard[-1].id, None
            continue

        seat, intent = _random_intent(state, rng)
        assert intent is not None, f"nobody can move: seat {seat}, phase {state.phase}"
        top_before = state.discard[-1].id if state.discard else None
        stock_before = len(state.stock)
        try:
            state, events = apply(state, intent)
        except AppError:
            # e.g. a forced pickup that cannot be laid — fall back to the policy.
            intent = ai.next_bot_intent(state, seat)
            assert intent is not None, f"stuck after rejection: seat {seat}, phase {state.phase}"
            state, events = apply(state, intent)

        match intent:
            case DrawStock():
                offer = state.free_card
                offered = offer.card_id if offer is not None else None
                if top_before == live:
                    # A refusal of the live card: it goes to the following seats
                    # (3+ players; the reshuffle can empty the pile first).
                    reshuffled = len(state.stock) > stock_before
                    if num_players >= 3 and not reshuffled:
                        assert offered == live, (
                            f"live card {live} was not offered (seed={seed}, "
                            f"players={num_players}, offer={offer})"
                        )
                else:
                    assert offered is None, (
                        f"settled card {top_before} offered again (live={live}, "
                        f"seed={seed}, players={num_players})"
                    )
                live = None
            case DrawDiscard():
                assert top_before == live, (
                    f"seat {seat} took the settled card {top_before} (live={live}, "
                    f"seed={seed}, players={num_players})"
                )
                held, live = live, None
            case ReturnDiscard():
                live, held = held, None
            case ClaimFreeCard():
                assert any(e.type == "free_card_claimed" for e in events)
                live = None
            case Discard():
                live, held = state.discard[-1].id, None

    pytest.fail(f"game did not finish in {MAX_STEPS} steps (seed={seed})")


@pytest.mark.parametrize("num_players", [2, 3, 4])
@pytest.mark.parametrize("seed", range(12))
def test_free_card_window_holds_under_random_play(num_players: int, seed: int) -> None:
    _play(num_players, seed)
