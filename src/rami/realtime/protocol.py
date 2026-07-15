"""WebSocket wire protocol: client intents in, server snapshots/events out,
plus the per-seat redaction that turns the engine state into what each player is
allowed to see."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

from rami.game.cards import Card, rank_label
from rami.game.contracts import contract_for
from rami.game.intents import (
    ClaimFreeCard,
    Discard,
    DrawDiscard,
    DrawStock,
    Intent,
    LayMelds,
    LayOff,
    MeldSpec,
    PassFreeCard,
    RecoverJoker,
    ReturnDiscard,
)
from rami.game.melds import Meld, MeldKind, ReprCard, meld_points
from rami.game.state import Event, GameState, Phase

# --------------------------------------------------------------------------- #
# Client -> server messages
# --------------------------------------------------------------------------- #


class _Base(BaseModel):
    pass


class DrawStockMsg(_Base):
    type: Literal["draw_stock"]


class DrawDiscardMsg(_Base):
    type: Literal["draw_discard"]


class ClaimFreeCardMsg(_Base):
    type: Literal["claim_free_card"]


class PassFreeCardMsg(_Base):
    type: Literal["pass_free_card"]


class MeldSpecMsg(_Base):
    kind: MeldKind
    card_ids: list[int]


class LayMeldsMsg(_Base):
    type: Literal["lay_melds"]
    melds: list[MeldSpecMsg]


class LayOffMsg(_Base):
    type: Literal["lay_off"]
    meld_id: int
    card_id: int


class RecoverJokerMsg(_Base):
    type: Literal["recover_joker"]
    meld_id: int
    card_id: int


class DiscardMsg(_Base):
    type: Literal["discard"]
    card_id: int


class ReturnDiscardMsg(_Base):
    type: Literal["return_discard"]


class StartMsg(_Base):
    type: Literal["start"]


class NextRoundMsg(_Base):
    type: Literal["next_round"]


class ReadyMsg(_Base):
    type: Literal["ready"]
    ready: bool


ClientMessage = Annotated[
    DrawStockMsg
    | DrawDiscardMsg
    | ClaimFreeCardMsg
    | PassFreeCardMsg
    | LayMeldsMsg
    | LayOffMsg
    | RecoverJokerMsg
    | DiscardMsg
    | ReturnDiscardMsg
    | StartMsg
    | NextRoundMsg
    | ReadyMsg,
    Field(discriminator="type"),
]

client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


def to_engine_intent(seat: int, msg: ClientMessage) -> Intent | None:
    """Map an in-game client message to an engine intent (None for lobby/flow
    messages handled separately)."""
    match msg:
        case DrawStockMsg():
            return DrawStock(seat)
        case DrawDiscardMsg():
            return DrawDiscard(seat)
        case ClaimFreeCardMsg():
            return ClaimFreeCard(seat)
        case PassFreeCardMsg():
            return PassFreeCard(seat)
        case LayMeldsMsg():
            return LayMelds(seat, [MeldSpec(kind=m.kind, card_ids=m.card_ids) for m in msg.melds])
        case LayOffMsg():
            return LayOff(seat, msg.meld_id, msg.card_id)
        case RecoverJokerMsg():
            return RecoverJoker(seat, msg.meld_id, msg.card_id)
        case DiscardMsg():
            return Discard(seat, msg.card_id)
        case ReturnDiscardMsg():
            return ReturnDiscard(seat)
        case _:
            return None


# --------------------------------------------------------------------------- #
# Server -> client snapshot
# --------------------------------------------------------------------------- #


class CardView(BaseModel):
    id: int
    suit: str | None
    rank: int | None
    is_joker: bool
    label: str


class ReprView(BaseModel):
    suit: str | None
    rank: int
    label: str


class MeldView(BaseModel):
    id: int
    kind: str
    owner_seat: int
    cards: list[CardView]
    reprs: dict[int, ReprView]
    points: int


class ReqView(BaseModel):
    kind: str
    min_len: int


class ContractView(BaseModel):
    round_no: int
    label: str
    requirements: list[ReqView]


class PlayerView(BaseModel):
    seat: int
    name: str
    has_gone_out: bool
    hand_count: int
    round_score: int
    total_score: int
    connected: bool
    ready: bool
    is_turn: bool
    is_bot: bool


class FreeCardView(BaseModel):
    current_seat: int
    pending_seats: list[int]


class StandingView(BaseModel):
    seat: int
    name: str
    total: int


class Snapshot(BaseModel):
    type: Literal["snapshot"] = "snapshot"
    code: str
    you: int
    phase: str
    round_no: int
    turn_seat: int
    dealer_seat: int
    stock_count: int
    discard_top: CardView | None
    discard_count: int
    contract: ContractView | None
    free_card: FreeCardView | None
    taken_from_discard_id: int | None
    go_out_min_points: int
    players: list[PlayerView]
    your_hand: list[CardView]
    table_melds: list[MeldView]
    last_round_scores: dict[int, int]
    standings: list[StandingView] | None


class EventView(BaseModel):
    type: str
    data: dict[str, Any]


class EventsMsg(BaseModel):
    type: Literal["events"] = "events"
    events: list[EventView]


class ErrorMsg(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #


def card_view(card: Card) -> CardView:
    return CardView(
        id=card.id,
        suit=card.suit.value if card.suit else None,
        rank=card.rank,
        is_joker=card.is_joker,
        label=card.label,
    )


def _repr_view(rep: ReprCard) -> ReprView:
    # An unresolved joker shows its rank only — the suit is not yet determined.
    suit = rep.suit.value if rep.suit is not None else None
    label = f"{rank_label(rep.rank)}{suit}" if suit is not None else rank_label(rep.rank)
    return ReprView(suit=suit, rank=rep.rank, label=label)


def meld_view(meld: Meld) -> MeldView:
    return MeldView(
        id=meld.id,
        kind=meld.kind.value,
        owner_seat=meld.owner_seat,
        cards=[card_view(c) for c in meld.cards],
        reprs={cid: _repr_view(rep) for cid, rep in meld.represents.items()},
        points=meld_points(meld),
    )


def _contract_view(state: GameState) -> ContractView | None:
    if state.round_no < 1:
        return None
    c = contract_for(state.round_no)
    return ContractView(
        round_no=c.round_no,
        label=c.label(),
        requirements=[ReqView(kind=r.kind.value, min_len=r.min_len) for r in c.requirements],
    )


_TURN_PHASES = {Phase.AWAIT_DRAW, Phase.AWAIT_DISCARD}


def build_snapshot(
    code: str,
    state: GameState,
    seat: int,
    connected: list[bool],
    ready: list[bool],
    bots: list[bool] | None = None,
) -> Snapshot:
    bots = bots or []
    you = state.player(seat)
    players = [
        PlayerView(
            seat=p.seat,
            name=p.name,
            has_gone_out=p.has_gone_out,
            hand_count=len(p.hand),
            round_score=p.round_score,
            total_score=p.total_score,
            connected=connected[p.seat] if p.seat < len(connected) else False,
            ready=ready[p.seat] if p.seat < len(ready) else False,
            is_turn=(state.phase in _TURN_PHASES and state.turn_seat == p.seat),
            is_bot=bots[p.seat] if p.seat < len(bots) else False,
        )
        for p in state.players
    ]
    free_card = None
    if state.free_card is not None and state.free_card.pending_seats:
        free_card = FreeCardView(
            current_seat=state.free_card.pending_seats[0],
            pending_seats=list(state.free_card.pending_seats),
        )
    standings = None
    if state.phase == Phase.GAME_OVER:
        ordered = sorted(state.players, key=lambda p: p.total_score)
        standings = [StandingView(seat=p.seat, name=p.name, total=p.total_score) for p in ordered]

    return Snapshot(
        code=code,
        you=seat,
        phase=state.phase.value,
        round_no=state.round_no,
        turn_seat=state.turn_seat,
        dealer_seat=state.dealer_seat,
        stock_count=len(state.stock),
        discard_top=card_view(state.discard[-1]) if state.discard else None,
        discard_count=len(state.discard),
        contract=_contract_view(state),
        free_card=free_card,
        taken_from_discard_id=state.taken_from_discard_id,
        go_out_min_points=40,
        players=players,
        your_hand=[card_view(c) for c in you.hand],
        table_melds=[meld_view(m) for m in state.table_melds],
        last_round_scores=dict(state.last_round_scores),
        standings=standings,
    )


def events_payload(events: list[Event]) -> EventsMsg:
    return EventsMsg(events=[EventView(type=e.type, data=e.data) for e in events])


# keep MeldKind importable for callers building specs
__all__ = [
    "ClientMessage",
    "ErrorMsg",
    "EventsMsg",
    "MeldKind",
    "Snapshot",
    "build_snapshot",
    "client_message_adapter",
    "events_payload",
    "to_engine_intent",
]
