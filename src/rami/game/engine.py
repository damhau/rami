"""The rules engine: `apply(state, intent) -> (state, events)` plus round setup.

Every public function returns a *new* state (the input is never mutated), so a
rejected move leaves the caller's state untouched. The functions are pure and
deterministic: randomness comes only from `state.rng_seed` + `shuffle_count`.
"""

from __future__ import annotations

import copy
import random

from rami.core.exceptions import ContractNotMet, IllegalMove, NotYourTurn

from .cards import Card, build_deck
from .contracts import TOTAL_ROUNDS, LaidMeld, contract_for, satisfies_contract
from .intents import (
    ClaimFreeCard,
    Discard,
    DrawDiscard,
    DrawStock,
    Intent,
    LayMelds,
    LayOff,
    PassFreeCard,
    RecoverJoker,
)
from .melds import (
    Meld,
    MeldKind,
    arrange_run,
    cards_points,
    meld_points,
    repr_matches_card,
    try_lay_off,
    validate_meld,
)
from .scoring import hand_score
from .state import Event, FreeCardOffer, GameState, Phase, PlayerState

HAND_SIZE = 13
GO_OUT_MIN_POINTS = 40


# --------------------------------------------------------------------------- #
# Construction & round setup
# --------------------------------------------------------------------------- #


def new_game(player_names: list[str], rng_seed: int = 0) -> GameState:
    players = [PlayerState(seat=i, name=name) for i, name in enumerate(player_names)]
    return GameState(players=players, phase=Phase.LOBBY, rng_seed=rng_seed)


def _make_rng(state: GameState) -> random.Random:
    return random.Random((state.rng_seed * 1_000_003) ^ ((state.shuffle_count + 1) * 2_654_435_761))


def start_round(state: GameState) -> tuple[GameState, list[Event]]:
    """Begin round 1 (from LOBBY) or the next round (from ROUND_OVER)."""
    if state.phase not in (Phase.LOBBY, Phase.ROUND_OVER):
        raise IllegalMove("cannot start a round now")
    s = copy.deepcopy(state)
    n = s.num_players

    if s.phase == Phase.LOBBY:
        s.round_no = 1
        # dealer stays as configured (seat 0); starter is the player after.
    else:
        s.round_no += 1
        s.dealer_seat = (s.dealer_seat + 1) % n

    rng = _make_rng(s)
    s.shuffle_count += 1
    deck = build_deck(rng)

    for p in s.players:
        p.hand = []
        p.has_gone_out = False
        p.round_score = 0
    s.table_melds = []
    s.next_meld_id = 0
    s.taken_from_discard_id = None
    s.free_card = None

    # Deal 13 each, flip one to the discard, the rest is the stock.
    for _ in range(HAND_SIZE):
        for p in s.players:
            p.hand.append(deck.pop())
    s.discard = [deck.pop()]
    s.stock = deck

    s.turn_seat = (s.dealer_seat + 1) % n
    s.phase = Phase.AWAIT_DRAW
    events = [Event("round_started", {"round_no": s.round_no, "turn_seat": s.turn_seat})]
    return s, events


# --------------------------------------------------------------------------- #
# Apply
# --------------------------------------------------------------------------- #


def apply(state: GameState, intent: Intent) -> tuple[GameState, list[Event]]:
    s = copy.deepcopy(state)
    events: list[Event] = []

    match intent:
        case DrawStock():
            _draw_stock(s, intent, events)
        case DrawDiscard():
            _draw_discard(s, intent, events)
        case ClaimFreeCard():
            _free_card_decision(s, intent.seat, claim=True, events=events)
        case PassFreeCard():
            _free_card_decision(s, intent.seat, claim=False, events=events)
        case LayMelds():
            _lay_melds(s, intent, events)
        case LayOff():
            _lay_off(s, intent, events)
        case RecoverJoker():
            _recover_joker(s, intent, events)
        case Discard():
            _discard(s, intent, events)
        case _:  # pragma: no cover - exhaustive above
            raise IllegalMove("unknown intent")

    return s, events


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #


def _require_turn(s: GameState, seat: int) -> None:
    if seat != s.turn_seat:
        raise NotYourTurn()


def _hand_card(p: PlayerState, card_id: int) -> Card:
    card = next((c for c in p.hand if c.id == card_id), None)
    if card is None:
        raise IllegalMove(f"card {card_id} is not in hand")
    return card


def _take_from_hand(p: PlayerState, card_id: int) -> Card:
    card = _hand_card(p, card_id)
    p.hand = [c for c in p.hand if c.id != card_id]
    return card


# --------------------------------------------------------------------------- #
# Drawing
# --------------------------------------------------------------------------- #


def _draw_one_from_stock(s: GameState) -> Card:
    if not s.stock:
        if len(s.discard) <= 1:
            raise IllegalMove("stock and discard are exhausted")
        top = s.discard[-1]
        rest = s.discard[:-1]
        rng = _make_rng(s)
        s.shuffle_count += 1
        rng.shuffle(rest)
        s.stock = rest
        s.discard = [top]
    return s.stock.pop()


def _draw_stock(s: GameState, intent: DrawStock, events: list[Event]) -> None:
    if s.phase != Phase.AWAIT_DRAW:
        raise IllegalMove("you cannot draw now")
    _require_turn(s, intent.seat)
    card = _draw_one_from_stock(s)
    s.player(intent.seat).hand.append(card)
    events.append(Event("drew", {"seat": intent.seat, "source": "stock"}))

    # The drawer proceeds immediately — they are never blocked by the offer.
    s.phase = Phase.AWAIT_DISCARD

    # With 3+ players, drawing from stock refuses the visible discard, which the
    # following players may then claim for free. The offer stays open (non-blocking)
    # until the drawer discards, at which point it is dropped (§3.7).
    if s.num_players >= 3 and s.discard:
        pending = [(intent.seat + k) % s.num_players for k in range(1, s.num_players)]
        s.free_card = FreeCardOffer(pending_seats=pending, resume_seat=intent.seat)
        events.append(Event("free_card_offered", {"seats": list(pending)}))


def _draw_discard(s: GameState, intent: DrawDiscard, events: list[Event]) -> None:
    if s.phase != Phase.AWAIT_DRAW:
        raise IllegalMove("you cannot draw now")
    _require_turn(s, intent.seat)
    if not s.discard:
        raise IllegalMove("the discard pile is empty")
    card = s.discard.pop()
    s.player(intent.seat).hand.append(card)
    # Taking the discard obliges laying it this turn (a go-out if not yet out).
    s.taken_from_discard_id = card.id
    s.phase = Phase.AWAIT_DISCARD
    events.append(Event("drew", {"seat": intent.seat, "source": "discard", "card_id": card.id}))


# --------------------------------------------------------------------------- #
# Free-card chain
# --------------------------------------------------------------------------- #


def _free_card_decision(s: GameState, seat: int, claim: bool, events: list[Event]) -> None:
    offer = s.free_card
    if offer is None or not offer.pending_seats:
        raise IllegalMove("there is no free card to decide on")
    if seat != offer.pending_seats[0]:
        raise IllegalMove("it is not your free-card decision")

    if claim:
        if not s.discard:
            raise IllegalMove("the free card is gone")
        card = s.discard.pop()
        s.player(seat).hand.append(card)
        events.append(Event("free_card_claimed", {"seat": seat, "card_id": card.id}))
        s.free_card = None  # a single card — claiming it ends the offer
        return

    events.append(Event("free_card_passed", {"seat": seat}))
    offer.pending_seats.pop(0)
    if not offer.pending_seats:
        s.free_card = None


# --------------------------------------------------------------------------- #
# Melding / going out
# --------------------------------------------------------------------------- #


def _lay_melds(s: GameState, intent: LayMelds, events: list[Event]) -> None:
    if s.phase != Phase.AWAIT_DISCARD:
        raise IllegalMove("you can only lay melds after drawing, before discarding")
    _require_turn(s, intent.seat)
    if not intent.melds:
        raise IllegalMove("no melds provided")

    player = s.player(intent.seat)

    # Resolve and validate every group against the *current* hand.
    seen: set[int] = set()
    built: list[Meld] = []
    for spec in intent.melds:
        if len(spec.card_ids) < 3:
            raise IllegalMove("a meld needs at least 3 cards")
        cards: list[Card] = []
        for cid in spec.card_ids:
            if cid in seen:
                raise IllegalMove(f"card {cid} used twice")
            seen.add(cid)
            cards.append(_hand_card(player, cid))
        validate_meld(spec.kind, cards)
        if spec.kind == MeldKind.RUN:
            # Accept the cards in any order; canonicalize the run so joker
            # representations and the table display come out right.
            arranged = arrange_run(cards)
            assert arranged is not None  # validate_meld just passed
            cards = arranged
        built.append(Meld(id=-1, kind=spec.kind, cards=cards, owner_seat=intent.seat))

    if not player.has_gone_out:
        # This is the single go-out action: contract + >= 40 points.
        contract = contract_for(s.round_no)
        laid = [LaidMeld(kind=m.kind, length=len(m.cards)) for m in built]
        if not satisfies_contract(contract, laid):
            raise ContractNotMet(f"melds do not satisfy contract: {contract.label()}")
        total = sum(cards_points(m.cards, m.kind) for m in built)
        if total < GO_OUT_MIN_POINTS:
            raise ContractNotMet(f"need >= {GO_OUT_MIN_POINTS} points, laid {total}")
        if s.taken_from_discard_id is not None and s.taken_from_discard_id not in seen:
            raise IllegalMove("the card taken from the discard must be used in your melds")

    # Commit: assign ids, move cards out of hand, place on the table.
    for m in built:
        m.id = s.next_meld_id
        s.next_meld_id += 1
        m.refresh()
        s.table_melds.append(m)
    laid_ids = {c.id for m in built for c in m.cards}
    player.hand = [c for c in player.hand if c.id not in laid_ids]

    if not player.has_gone_out:
        player.has_gone_out = True
        events.append(Event("went_out", {"seat": intent.seat, "round_no": s.round_no}))
    events.append(Event("melded", {"seat": intent.seat, "meld_ids": [m.id for m in built]}))

    if s.taken_from_discard_id is not None and s.taken_from_discard_id in laid_ids:
        s.taken_from_discard_id = None

    if not player.hand:
        _end_round(s, intent.seat, events)


def _lay_off(s: GameState, intent: LayOff, events: list[Event]) -> None:
    if s.phase != Phase.AWAIT_DISCARD:
        raise IllegalMove("you can only lay off after drawing, before discarding")
    _require_turn(s, intent.seat)
    player = s.player(intent.seat)
    if not player.has_gone_out:
        raise IllegalMove("you must go out before laying off")
    meld = s.meld(intent.meld_id)
    if meld is None:
        raise IllegalMove(f"meld {intent.meld_id} not found")
    card = _hand_card(player, intent.card_id)
    new_cards = try_lay_off(meld, card)
    if new_cards is None:
        raise IllegalMove(f"{card.label} cannot extend that meld")
    meld.cards = new_cards
    meld.refresh()
    _take_from_hand(player, intent.card_id)
    events.append(Event("laid_off", {"seat": intent.seat, "meld_id": meld.id, "card_id": card.id}))
    if s.taken_from_discard_id == card.id:
        s.taken_from_discard_id = None
    if not player.hand:
        _end_round(s, intent.seat, events)


def _recover_joker(s: GameState, intent: RecoverJoker, events: list[Event]) -> None:
    if s.phase != Phase.AWAIT_DISCARD:
        raise IllegalMove("you can only recover a joker on your turn, before discarding")
    _require_turn(s, intent.seat)
    player = s.player(intent.seat)
    if not player.has_gone_out:
        raise IllegalMove("you must go out before recovering jokers")
    meld = s.meld(intent.meld_id)
    if meld is None:
        raise IllegalMove(f"meld {intent.meld_id} not found")
    real = _hand_card(player, intent.card_id)
    if real.is_joker:
        raise IllegalMove("you recover a joker by laying a real card")

    joker_idx = next(
        (
            i
            for i, c in enumerate(meld.cards)
            if c.is_joker
            and (rep := meld.represents.get(c.id)) is not None
            and repr_matches_card(rep, real)
        ),
        None,
    )
    if joker_idx is None:
        raise IllegalMove(f"no joker in that meld represents {real.label}")

    joker = meld.cards[joker_idx]
    meld.cards[joker_idx] = real
    meld.refresh()
    _take_from_hand(player, intent.card_id)
    player.hand.append(joker)
    # Laying the exact card to recover a joker discharges the discard-pickup
    # obligation (same as lay-off), so the turn can finish on a discard.
    if s.taken_from_discard_id == real.id:
        s.taken_from_discard_id = None
    events.append(
        Event("recovered_joker", {"seat": intent.seat, "meld_id": meld.id, "joker_id": joker.id})
    )


# --------------------------------------------------------------------------- #
# Discard & round/game end
# --------------------------------------------------------------------------- #


def _discard(s: GameState, intent: Discard, events: list[Event]) -> None:
    if s.phase != Phase.AWAIT_DISCARD:
        raise IllegalMove("you can only discard after drawing")
    _require_turn(s, intent.seat)
    if s.taken_from_discard_id is not None:
        raise IllegalMove("you must lay the card taken from the discard before discarding")
    player = s.player(intent.seat)
    # Discarding ends the turn, closing any still-open free-card offer (§3.7).
    s.free_card = None
    card = _take_from_hand(player, intent.card_id)
    s.discard.append(card)
    events.append(Event("discarded", {"seat": intent.seat, "card_id": card.id}))

    if not player.hand:
        _end_round(s, intent.seat, events)
        return

    s.turn_seat = (s.turn_seat + 1) % s.num_players
    s.phase = Phase.AWAIT_DRAW


def _end_round(s: GameState, winner_seat: int, events: list[Event]) -> None:
    s.last_round_scores = {}
    for p in s.players:
        p.round_score = 0 if p.seat == winner_seat else hand_score(p.hand)
        p.total_score += p.round_score
        s.last_round_scores[p.seat] = p.round_score
    s.taken_from_discard_id = None
    s.free_card = None
    events.append(
        Event(
            "round_over",
            {
                "round_no": s.round_no,
                "winner_seat": winner_seat,
                "round_scores": dict(s.last_round_scores),
                "totals": {p.seat: p.total_score for p in s.players},
            },
        )
    )
    if s.round_no >= TOTAL_ROUNDS:
        s.phase = Phase.GAME_OVER
        standings = sorted(s.players, key=lambda p: p.total_score)
        events.append(
            Event(
                "game_over",
                {
                    "standings": [
                        {"seat": p.seat, "name": p.name, "total": p.total_score} for p in standings
                    ]
                },
            )
        )
    else:
        s.phase = Phase.ROUND_OVER


__all__ = ["GO_OUT_MIN_POINTS", "HAND_SIZE", "apply", "meld_points", "new_game", "start_round"]
