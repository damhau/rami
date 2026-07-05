"""A heuristic computer player.

`next_bot_intent(state, seat)` returns the single next move for a bot seat, or
None when the bot has nothing to do. The transport loops it (applying each move)
until the turn passes back to a human. The policy is pure — no I/O, no globals —
so it is unit-testable and deterministic.

Strategy (intentionally simple, not expert):
- Always draw from the stock and always pass on free cards (never takes on the
  discard obligation, so it can never soft-lock a turn).
- On the discard step, greedily extract the highest-value melds it can. If those
  melds satisfy the round contract and total >= 40, it goes out. After going out
  it lays off onto table melds and lays any further melds it can.
- It discards the highest-value card that is not part of any meld it could build.
"""

from __future__ import annotations

from collections import defaultdict

from .cards import ALL_SUITS, MIN_RANK, RANK_ACE, RANK_ACE_HIGH, Card, card_hand_value
from .contracts import LaidMeld, contract_for, satisfies_contract
from .intents import (
    Discard,
    DrawStock,
    Intent,
    LayMelds,
    LayOff,
    MeldSpec,
    PassFreeCard,
)
from .melds import (
    MeldKind,
    arrange_run,
    cards_points,
    is_valid_run,
    is_valid_set,
    try_lay_off,
)
from .state import GameState, Phase, PlayerState

GO_OUT_MIN_POINTS = 40
_RUN_LENGTHS = (3, 4, 5)


# --------------------------------------------------------------------------- #
# Candidate melds
# --------------------------------------------------------------------------- #


def _set_candidates(cards: list[Card]) -> list[tuple[MeldKind, list[Card]]]:
    jokers = [c for c in cards if c.is_joker]
    by_rank: dict[int, list[Card]] = defaultdict(list)
    for c in cards:
        if not c.is_joker:
            by_rank[c.rank].append(c)  # type: ignore[index]

    out: list[tuple[MeldKind, list[Card]]] = []
    for reals in by_rank.values():
        # Prefer distinct suits first, then any second-deck copies.
        seen: set[str] = set()
        distinct: list[Card] = []
        extra: list[Card] = []
        for c in reals:
            assert c.suit is not None
            (extra if c.suit in seen else distinct).append(c)
            seen.add(c.suit)
        ordered = distinct + extra
        for length in range(3, len(ordered) + len(jokers) + 1):
            use_reals = ordered[: min(length, len(ordered))]
            need_j = length - len(use_reals)
            if need_j > len(jokers):
                break
            cand = [*use_reals, *jokers[:need_j]]
            if is_valid_set(cand):
                out.append((MeldKind.SET, cand))
    return out


def _run_candidates(cards: list[Card]) -> list[tuple[MeldKind, list[Card]]]:
    jokers = [c for c in cards if c.is_joker]
    out: list[tuple[MeldKind, list[Card]]] = []
    for suit in ALL_SUITS:
        by_rank: dict[int, Card] = {}
        for c in cards:
            if not c.is_joker and c.suit == suit and c.rank not in by_rank:
                by_rank[c.rank] = c  # type: ignore[index]
        if not by_rank:
            continue
        for start in range(MIN_RANK, RANK_ACE_HIGH + 1):
            for length in _RUN_LENGTHS:
                end = start + length - 1
                if end > RANK_ACE_HIGH:
                    break
                if start == MIN_RANK and end == RANK_ACE_HIGH:
                    continue  # no full circle
                reals: list[Card] = []
                missing = 0
                for rank in range(start, end + 1):
                    phys = RANK_ACE if rank == RANK_ACE_HIGH else rank
                    card = by_rank.get(phys)
                    if card is not None:
                        reals.append(card)
                    else:
                        missing += 1
                if reals and missing <= len(jokers):
                    cand = [*reals, *jokers[:missing]]
                    if is_valid_run(cand):
                        out.append((MeldKind.RUN, cand))
    return out


def _all_candidates(cards: list[Card]) -> list[tuple[MeldKind, list[Card]]]:
    return _set_candidates(cards) + _run_candidates(cards)


def _meld_points(kind: MeldKind, cards: list[Card]) -> int:
    """Points the *engine* will credit for this meld. Runs must be scored on the
    arranged order, because a joker's value depends on where it lands and the
    engine re-orders runs with `arrange_run` (preferring the lowest start)."""
    if kind == MeldKind.RUN:
        arranged = arrange_run(cards)
        if arranged is None:
            return 0
        return cards_points(arranged, MeldKind.RUN)
    return cards_points(cards, kind)


def _greedy_melds(cards: list[Card]) -> list[tuple[MeldKind, list[Card]]]:
    """Repeatedly pull the highest-value valid meld out of `cards`."""
    pool = list(cards)
    result: list[tuple[MeldKind, list[Card]]] = []
    while True:
        cands = _all_candidates(pool)
        if not cands:
            break
        best = max(cands, key=lambda kc: _meld_points(kc[0], kc[1]))
        result.append(best)
        used = {c.id for c in best[1]}
        pool = [c for c in pool if c.id not in used]
    return result


# --------------------------------------------------------------------------- #
# Move selection
# --------------------------------------------------------------------------- #


def _find_go_out(state: GameState, p: PlayerState) -> Intent | None:
    melds = _greedy_melds(p.hand)
    if not melds:
        return None
    laid = [LaidMeld(kind=kind, length=len(cards)) for kind, cards in melds]
    if not satisfies_contract(contract_for(state.round_no), laid):
        return None
    total = sum(_meld_points(kind, cards) for kind, cards in melds)
    if total < GO_OUT_MIN_POINTS:
        return None
    specs = [MeldSpec(kind=kind, card_ids=[c.id for c in cards]) for kind, cards in melds]
    return LayMelds(p.seat, specs)


def _find_post_go_out_move(state: GameState, p: PlayerState) -> Intent | None:
    # Lay off single cards onto any table meld.
    for card in p.hand:
        if card.is_joker:
            continue
        for meld in state.table_melds:
            if try_lay_off(meld, card) is not None:
                return LayOff(p.seat, meld.id, card.id)
    # Otherwise lay a fresh meld if one is available.
    melds = _greedy_melds(p.hand)
    if melds:
        kind, cards = melds[0]
        return LayMelds(p.seat, [MeldSpec(kind=kind, card_ids=[c.id for c in cards])])
    return None


def _choose_discard(p: PlayerState) -> Intent:
    used = {c.id for _, cards in _greedy_melds(p.hand) for c in cards}
    free = [c for c in p.hand if c.id not in used and not c.is_joker]
    pool = free or [c for c in p.hand if not c.is_joker] or p.hand
    worst = max(pool, key=card_hand_value)
    return Discard(p.seat, worst.id)


def next_bot_intent(state: GameState, seat: int) -> Intent | None:
    """The next move for bot `seat`, or None if it has nothing to do now."""
    p = state.player(seat)

    # A free card may be offered to a bot even when it is not its turn. Keep it
    # simple: always pass (never take on extra cards / the go-out obligation).
    offer = state.free_card
    if offer is not None and offer.pending_seats and offer.pending_seats[0] == seat:
        return PassFreeCard(seat)

    if state.turn_seat != seat:
        return None

    if state.phase == Phase.AWAIT_DRAW:
        return DrawStock(seat)

    if state.phase == Phase.AWAIT_DISCARD:
        if not p.has_gone_out:
            go = _find_go_out(state, p)
            if go is not None:
                return go
        else:
            move = _find_post_go_out_move(state, p)
            if move is not None:
                return move
        return _choose_discard(p)

    return None


__all__ = ["next_bot_intent"]
