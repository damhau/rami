"""A heuristic computer player — aims for a "decent club player".

`next_bot_intent(state, seat)` returns the single next move for a bot seat, or
None when the bot has nothing to do. The transport loops it (applying each move)
until the turn passes back to a human. The policy is pure — no I/O, no globals —
so it is unit-testable and deterministic.

Strategy:
- Drawing: takes the face-up discard when it enables an immediate go-out (before
  going out) or can be laid this turn (after), else draws from the stock.
- Free cards (3+ players): claims one that completes a meld / can be laid off,
  else passes.
- Going out: a backtracking search covers the round contract with disjoint melds
  and adds supplementary melds to reach the 40-point minimum.
- Discarding: keeps cards that belong to a meld or a promising partial (pairs,
  near-runs) and sheds the least useful one, breaking ties by shedding points.
"""

from __future__ import annotations

from collections import defaultdict

from .cards import ALL_SUITS, MIN_RANK, RANK_ACE, RANK_ACE_HIGH, Card, card_hand_value
from .contracts import Requirement, contract_for
from .intents import (
    ClaimFreeCard,
    Discard,
    DrawDiscard,
    DrawStock,
    Intent,
    LayMelds,
    LayOff,
    MeldSpec,
    PassFreeCard,
    ReturnDiscard,
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

Meld = tuple[MeldKind, list[Card]]


# --------------------------------------------------------------------------- #
# Candidate melds
# --------------------------------------------------------------------------- #


def _set_candidates(cards: list[Card]) -> list[Meld]:
    jokers = [c for c in cards if c.is_joker]
    by_rank: dict[int, list[Card]] = defaultdict(list)
    for c in cards:
        if not c.is_joker:
            by_rank[c.rank].append(c)  # type: ignore[index]

    out: list[Meld] = []
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


def _run_candidates(cards: list[Card]) -> list[Meld]:
    jokers = [c for c in cards if c.is_joker]
    out: list[Meld] = []
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


def _all_candidates(cards: list[Card]) -> list[Meld]:
    return _set_candidates(cards) + _run_candidates(cards)


def _meld_points(kind: MeldKind, cards: list[Card]) -> int:
    """Points the *engine* will credit for this meld. Runs are scored on the
    arranged order (a joker's value depends on where it lands, and the engine
    re-orders runs with `arrange_run`, preferring the lowest start)."""
    if kind == MeldKind.RUN:
        arranged = arrange_run(cards)
        if arranged is None:
            return 0
        return cards_points(arranged, MeldKind.RUN)
    return cards_points(cards, kind)


def _greedy_melds(cards: list[Card]) -> list[Meld]:
    """Repeatedly pull the highest-value valid meld out of `cards` (disjoint)."""
    pool = list(cards)
    result: list[Meld] = []
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
# Going out: cover the contract with disjoint melds, reach 40 points
# --------------------------------------------------------------------------- #


def _cover_contract(
    cards: list[Card], reqs: tuple[Requirement, ...], require_id: int | None = None
) -> list[Meld] | None:
    """Find disjoint melds covering every requirement (plus supplementary melds)
    that total >= 40, or None. If `require_id` is given, the taken discard card
    must end up in one of the laid melds."""
    candidates = _all_candidates(cards)
    best: list[Meld] | None = None
    best_total = -1

    def consider(chosen: list[Meld], used: set[int]) -> None:
        nonlocal best, best_total
        extras = _greedy_melds([c for c in cards if c.id not in used])
        melds = chosen + extras
        all_ids = used | {c.id for _, cs in extras for c in cs}
        if require_id is not None and require_id not in all_ids:
            return
        # A turn always ends on a discard (§3.10): the go-out must leave at least
        # one card in hand to discard — never lay the whole hand.
        if len(all_ids) >= len(cards):
            return
        total = sum(_meld_points(k, cs) for k, cs in melds)
        if total >= GO_OUT_MIN_POINTS and total > best_total:
            best_total = total
            best = melds

    def backtrack(i: int, used: set[int], chosen: list[Meld]) -> None:
        if i == len(reqs):
            consider(chosen, used)
            return
        req = reqs[i]
        for kind, cs in candidates:
            if kind != req.kind or len(cs) < req.min_len:
                continue
            ids = {c.id for c in cs}
            if ids & used:
                continue
            backtrack(i + 1, used | ids, [*chosen, (kind, cs)])

    backtrack(0, set(), [])
    return best


def _find_go_out(state: GameState, p: PlayerState) -> Intent | None:
    reqs = contract_for(state.round_no).requirements
    melds = _cover_contract(p.hand, reqs, state.taken_from_discard_id)
    if not melds:
        return None
    specs = [MeldSpec(kind=kind, card_ids=[c.id for c in cards]) for kind, cards in melds]
    return LayMelds(p.seat, specs)


# --------------------------------------------------------------------------- #
# Using the taken discard card / after going out
# --------------------------------------------------------------------------- #


def _use_taken_card(state: GameState, p: PlayerState, taken_id: int) -> Intent | None:
    """Lay the just-taken discard card (lay-off, else a fresh meld). Only used
    after going out — the taken card is otherwise handled by the go-out search.
    Never plays the last card: a turn must still end on a discard (§3.10)."""
    card = next((c for c in p.hand if c.id == taken_id), None)
    if card is None:
        return None
    if len(p.hand) > 1:
        for meld in state.table_melds:
            if try_lay_off(meld, card) is not None:
                return LayOff(p.seat, meld.id, taken_id)
    for kind, cs in _all_candidates(p.hand):
        if taken_id in {c.id for c in cs} and len(cs) < len(p.hand):
            return LayMelds(p.seat, [MeldSpec(kind=kind, card_ids=[c.id for c in cs])])
    return None


def _find_post_go_out_move(state: GameState, p: PlayerState) -> Intent | None:
    """Shed one more card onto the table, if possible without emptying the hand.

    Prefer laying off the highest-penalty card first (never discard a card that
    has a legal table play — issue #5, §3.9), then a fresh supplementary meld.
    Always leaves at least one card so the turn can end on a discard (§3.10)."""
    if len(p.hand) <= 1:
        return None  # must keep the last card to discard
    # Exactly one card is kept back for the mandatory discard, so lay off the
    # most expensive placeable card first — a placeable joker must never end up
    # as the forced final discard (issue #14: that hands 25 pts to the pile).
    for card in sorted(p.hand, key=card_hand_value, reverse=True):
        for meld in state.table_melds:
            if try_lay_off(meld, card) is not None:
                return LayOff(p.seat, meld.id, card.id)
    # Otherwise lay a fresh meld if one is available (and it leaves a spare).
    for kind, cards in _greedy_melds(p.hand):
        if len(cards) < len(p.hand):
            return LayMelds(p.seat, [MeldSpec(kind=kind, card_ids=[c.id for c in cards])])
    return None


# --------------------------------------------------------------------------- #
# Drawing / free cards
# --------------------------------------------------------------------------- #


def _out_can_use(state: GameState, p: PlayerState, card: Card) -> bool:
    """Can the taken discard actually be used this turn?

    Must mirror `_use_taken_card` exactly — including the keep-a-card-to-discard
    rule (§3.10) — otherwise the bot takes a card, finds it cannot lay it, returns
    it, and repeats forever (the DrawDiscard ↔ ReturnDiscard livelock, issue #16).
    """
    hand_after = len(p.hand) + 1  # hand size once the card is taken
    if hand_after > 1 and any(try_lay_off(meld, card) is not None for meld in state.table_melds):
        return True
    return any(
        card.id in {c.id for c in cs} and len(cs) < hand_after
        for _, cs in _all_candidates([*p.hand, card])
    )


def _should_take_discard(state: GameState, p: PlayerState) -> bool:
    top = state.discard[-1]
    if not p.has_gone_out:
        # Taking obliges an immediate go-out, so only take it if that go-out exists.
        reqs = contract_for(state.round_no).requirements
        return _cover_contract([*p.hand, top], reqs, require_id=top.id) is not None
    return _out_can_use(state, p, top)


def _useful_free_card(state: GameState, p: PlayerState, card: Card) -> bool:
    """A free card is worth taking only if it completes a meld with cards already
    in hand, or (once out) can be laid off."""
    for _, cs in _all_candidates([*p.hand, card]):
        ids = {c.id for c in cs}
        if card.id in ids and sum(1 for c in cs if not c.is_joker and c.id != card.id) >= 2:
            return True
    if p.has_gone_out:
        return any(try_lay_off(meld, card) is not None for meld in state.table_melds)
    return False


# --------------------------------------------------------------------------- #
# Discarding: keep useful cards, shed the least useful (and highest-value)
# --------------------------------------------------------------------------- #


def _keep_score(card: Card, hand: list[Card], locked: set[int]) -> int:
    if card.is_joker:
        return 10_000
    score = 0
    if card.id in locked:
        score += 1_000  # already part of a complete meld we're holding
    assert card.rank is not None
    same_rank = sum(1 for o in hand if o.id != card.id and not o.is_joker and o.rank == card.rank)
    if same_rank:
        score += 40 + 15 * same_rank  # a pair/triple toward a set
    for o in hand:
        if o.id == card.id or o.is_joker or o.suit != card.suit or o.rank == card.rank:
            continue
        assert o.rank is not None
        gap = abs(o.rank - card.rank)
        if gap == 1:
            score += 25  # neighbour toward a run
        elif gap == 2:
            score += 12  # one-gap toward a run
    return score


def _choose_discard(p: PlayerState) -> Intent:
    hand = p.hand
    locked = {c.id for _, cs in _greedy_melds(hand) for c in cs}
    # Shed the least useful card; among equally useless, shed the most points.
    worst = min(hand, key=lambda c: (_keep_score(c, hand, locked), -card_hand_value(c)))
    return Discard(p.seat, worst.id)


# --------------------------------------------------------------------------- #
# Move selection
# --------------------------------------------------------------------------- #


def next_bot_intent(state: GameState, seat: int) -> Intent | None:
    """The next move for bot `seat`, or None if it has nothing to do now."""
    p = state.player(seat)

    # A free card may be offered to a bot even when it is not its turn.
    offer = state.free_card
    if offer is not None and offer.pending_seats and offer.pending_seats[0] == seat:
        top = state.discard[-1] if state.discard else None
        if top is not None and _useful_free_card(state, p, top):
            return ClaimFreeCard(seat)
        return PassFreeCard(seat)

    if state.turn_seat != seat:
        return None

    if state.phase == Phase.AWAIT_DRAW:
        if state.discard and _should_take_discard(state, p):
            return DrawDiscard(seat)
        return DrawStock(seat)

    if state.phase == Phase.AWAIT_DISCARD:
        taken = state.taken_from_discard_id
        if not p.has_gone_out:
            go = _find_go_out(state, p)
            if go is not None:
                return go
            if taken is not None:
                return ReturnDiscard(seat)  # took the discard but can't go out with it
            return _choose_discard(p)
        # Already out.
        if taken is not None:
            move = _use_taken_card(state, p, taken)
            return move if move is not None else ReturnDiscard(seat)
        move = _find_post_go_out_move(state, p)
        return move if move is not None else _choose_discard(p)

    return None


__all__ = ["next_bot_intent"]
