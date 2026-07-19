"""Melds: sets (triplettes) and runs (suites), with joker logic.

A meld stores only its physical cards; what each joker *represents* is derived
deterministically from the meld's contents (no stored state to drift). This is
how joker auto-reassignment (§3.9 of DESIGN.md) and recovery are kept honest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from rami.core.exceptions import IllegalMove

from .cards import (
    ALL_SUITS,
    MIN_RANK,
    NUM_DECKS,
    RANK_ACE,
    RANK_ACE_HIGH,
    Card,
    Suit,
    rank_points,
)


class MeldKind(StrEnum):
    SET = "set"  # triplette: >=3 same rank
    RUN = "run"  # suite: >=3 consecutive, same suit


@dataclass(frozen=True)
class ReprCard:
    """The card a joker currently stands in for.

    `suit` is None while the joker's suit is still ambiguous — e.g. a set with
    two or more suits missing (§3.9): the rank is fixed but which suit the joker
    represents is not yet determined. An unresolved joker cannot be recovered
    until its suit is pinned down."""

    rank: int  # 1..14 (14 = Ace high)
    suit: Suit | None = None


@dataclass
class Meld:
    id: int
    kind: MeldKind
    cards: list[Card]
    owner_seat: int
    represents: dict[int, ReprCard] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        """Recompute joker representations from current cards."""
        self.represents = joker_representations(self.kind, self.cards)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def _split(cards: list[Card]) -> tuple[list[Card], list[Card]]:
    real = [c for c in cards if not c.is_joker]
    jokers = [c for c in cards if c.is_joker]
    return real, jokers


def set_rank(cards: list[Card]) -> int | None:
    """The shared rank of a set, or None if undefined/invalid."""
    real, _ = _split(cards)
    if not real:
        return None
    ranks = {c.rank for c in real}
    if len(ranks) != 1:
        return None
    return real[0].rank


def is_valid_set(cards: list[Card]) -> bool:
    if len(cards) < 3:
        return False
    real, jokers = _split(cards)
    if not real:
        return False
    if set_rank(cards) is None:
        return False
    per_suit: dict[Suit, int] = {}
    for c in real:
        assert c.suit is not None
        per_suit[c.suit] = per_suit.get(c.suit, 0) + 1
        # No more copies of a suit than there are decks.
        if per_suit[c.suit] > NUM_DECKS:
            return False
    # A second copy of a suit (a 2nd-deck card) is only legal once every suit is
    # already present — a triplet fills the four distinct suits first, then grows
    # with second-deck copies (DESIGN.md §3.9). Jokers can fill the missing suits.
    if any(count >= 2 for count in per_suit.values()):
        present = len(per_suit)
        if present + len(jokers) < len(ALL_SUITS):
            return False
    return True


def run_suit(cards: list[Card]) -> Suit | None:
    real, _ = _split(cards)
    if not real:
        return None
    suits = {c.suit for c in real}
    if len(suits) != 1:
        return None
    return real[0].suit


def _run_start(cards: list[Card]) -> int | None:
    """Find the starting rank of the run given the card order, or None.

    Each position i must hold rank `start + i`. A real Ace may be low (1) or
    high (14). No wrap-around (a single run cannot span both Ace ends).
    """
    real, _ = _split(cards)
    if not real:
        return None
    if run_suit(cards) is None:
        return None

    n = len(cards)
    candidate_starts: set[int] | None = None
    for i, c in enumerate(cards):
        if c.is_joker:
            continue
        assert c.rank is not None
        options = {RANK_ACE - i, RANK_ACE_HIGH - i} if c.rank == RANK_ACE else {c.rank - i}
        candidate_starts = options if candidate_starts is None else (candidate_starts & options)
        if not candidate_starts:
            return None

    if not candidate_starts:
        return None

    valid: list[int] = []
    for start in candidate_starts:
        end = start + n - 1
        if start < MIN_RANK or end > RANK_ACE_HIGH:
            continue
        if start == MIN_RANK and end == RANK_ACE_HIGH:
            continue  # full circle / both Ace ends — not allowed
        valid.append(start)
    if not valid:
        return None
    return min(valid)


def arrange_run(cards: list[Card]) -> list[Card] | None:
    """Order `cards` into a valid run regardless of input order, or None.

    Real cards go at their rank (an Ace may be low or high); jokers fill the
    remaining slots. Returns the left-to-right sequence so joker representations
    come out right. This makes runs order-independent: the caller may pass cards
    in any order (e.g. click order from the UI).
    """
    if len(cards) < 3:
        return None
    real, jokers = _split(cards)
    if not real or run_suit(cards) is None:
        return None

    n = len(cards)
    aces = [c for c in real if c.rank == RANK_ACE]
    fixed = [c for c in real if c.rank != RANK_ACE]

    # Try every low/high assignment for the aces (there are very few).
    for hi_mask in range(2 ** len(aces)):
        by_rank: dict[int, Card] = {}
        collision = False
        for c in fixed:
            assert c.rank is not None
            if c.rank in by_rank:
                collision = True  # two reals share a rank — not a run
                break
            by_rank[c.rank] = c
        for i, c in enumerate(aces):
            if collision:
                break
            rank = RANK_ACE_HIGH if (hi_mask >> i) & 1 else RANK_ACE
            if rank in by_rank:
                collision = True
                break
            by_rank[rank] = c
        if collision:
            continue

        ranks = sorted(by_rank)
        lo, hi = ranks[0], ranks[-1]
        # The window [start, start+n-1] must contain every real rank, stay within
        # bounds, and not span both Ace ends. Prefer the lowest valid start.
        for start in range(max(MIN_RANK, hi - n + 1), min(lo, RANK_ACE_HIGH - n + 1) + 1):
            end = start + n - 1
            if start == MIN_RANK and end == RANK_ACE_HIGH:
                continue  # full circle / both Ace ends — not allowed
            seq: list[Card] = []
            spare = list(jokers)
            for rank in range(start, end + 1):
                if rank in by_rank:
                    seq.append(by_rank[rank])
                elif spare:
                    seq.append(spare.pop(0))
                else:
                    seq = []
                    break
            if seq and not spare:
                return seq
    return None


def is_valid_run(cards: list[Card]) -> bool:
    return arrange_run(cards) is not None


def is_valid_run_order(cards: list[Card]) -> bool:
    """True if `cards` are *already* in a valid left-to-right run order.

    Lets the caller honour a player's chosen ordering — and therefore where each
    joker sits (§3.9) — instead of canonicalizing to the lowest arrangement."""
    return _run_start(cards) is not None


def run_bounds(cards: list[Card]) -> tuple[int, int] | None:
    """The (start, end) ranks of an ordered run, or None if not a valid order.

    Table runs are stored in order, so this gives the ranks a lay-off could
    extend: `start - 1` on the low side, `end + 1` on the high side."""
    start = _run_start(cards)
    if start is None:
        return None
    return start, start + len(cards) - 1


def is_valid_meld(kind: MeldKind, cards: list[Card]) -> bool:
    return is_valid_set(cards) if kind == MeldKind.SET else is_valid_run(cards)


def validate_meld(kind: MeldKind, cards: list[Card]) -> None:
    if not is_valid_meld(kind, cards):
        raise IllegalMove(f"not a valid {kind.value}: {[c.label for c in cards]}")


# --------------------------------------------------------------------------- #
# Joker representation
# --------------------------------------------------------------------------- #


def joker_representations(kind: MeldKind, cards: list[Card]) -> dict[int, ReprCard]:
    if kind == MeldKind.SET:
        return _set_joker_reprs(cards)
    return _run_joker_reprs(cards)


def _set_joker_reprs(cards: list[Card]) -> dict[int, ReprCard]:
    rank = set_rank(cards)
    real, jokers = _split(cards)
    if rank is None or not jokers:
        return {}
    per_suit: dict[Suit, int] = dict.fromkeys(ALL_SUITS, 0)
    for c in real:
        assert c.suit is not None
        per_suit[c.suit] += 1
    missing = [suit for suit in ALL_SUITS if per_suit[suit] == 0]
    # A joker's suit is only *determined* when the jokers must collectively cover
    # every still-missing suit (§3.9). With fewer jokers than missing suits, which
    # suit each joker stands for is ambiguous (e.g. A♠ A♥ + Joker → "A♦ or A♣"), so
    # the suit is left unresolved until an added card pins it down. Any jokers
    # beyond the missing suits are second-deck copies whose suit is likewise
    # ambiguous. Every joker still carries the rank, so its point value is exact.
    determined = missing if len(jokers) >= len(missing) else []
    out: dict[int, ReprCard] = {}
    for i, joker in enumerate(jokers):
        suit = determined[i] if i < len(determined) else None
        out[joker.id] = ReprCard(rank=rank, suit=suit)
    return out


def _run_joker_reprs(cards: list[Card]) -> dict[int, ReprCard]:
    start = _run_start(cards)
    suit = run_suit(cards)
    if start is None or suit is None:
        return {}
    out: dict[int, ReprCard] = {}
    for i, c in enumerate(cards):
        if c.is_joker:
            out[c.id] = ReprCard(suit=suit, rank=start + i)
    return out


def repr_matches_card(rep: ReprCard, card: Card) -> bool:
    """Does `card` (a real card) match what a joker represents?"""
    # An unresolved joker (suit still ambiguous) matches no concrete card, so it
    # cannot be recovered until its suit is pinned down (§3.9).
    if rep.suit is None or card.is_joker or card.suit != rep.suit:
        return False
    if rep.rank == RANK_ACE_HIGH:
        return card.rank == RANK_ACE
    return card.rank == rep.rank


# --------------------------------------------------------------------------- #
# Points
# --------------------------------------------------------------------------- #


def meld_points(meld: Meld) -> int:
    """Total laid value of a meld; a joker counts as the card it represents."""
    total = 0
    reps = meld.represents
    for c in meld.cards:
        if c.is_joker:
            rep = reps.get(c.id)
            total += rank_points(rep.rank) if rep is not None else 0
        else:
            assert c.rank is not None
            total += rank_points(c.rank)
    return total


def cards_points(cards: list[Card], kind: MeldKind) -> int:
    """Laid value of a not-yet-built meld (used to score a go-out action)."""
    return meld_points(Meld(id=-1, kind=kind, cards=list(cards), owner_seat=-1))


# --------------------------------------------------------------------------- #
# Laying off onto an existing meld
# --------------------------------------------------------------------------- #


def try_lay_off(meld: Meld, card: Card, as_rank: int | None = None) -> list[Card] | None:
    """Return the new card list if `card` legally extends `meld`, else None.

    For a joker laid onto a run, `as_rank` chooses which end it extends (the rank
    it should represent) — so a player can add a joker on the high side instead of
    always the lowest (§3.9 / issue #11). It is ignored for sets and real cards."""
    if meld.kind == MeldKind.SET:
        candidate = [*meld.cards, card]
        return candidate if is_valid_set(candidate) else None
    # Run with an explicit joker placement: put the joker at the chosen end and
    # keep that order if it forms a valid run.
    if card.is_joker and as_rank is not None:
        start = _run_start(meld.cards)
        if start is None:
            return None
        end = start + len(meld.cards) - 1
        if as_rank == end + 1:
            candidate = [*meld.cards, card]
        elif as_rank == start - 1:
            candidate = [card, *meld.cards]
        else:
            return None
        return candidate if is_valid_run_order(candidate) else None
    # Otherwise re-order the combined cards so the result stays a valid sequence.
    return arrange_run([*meld.cards, card])
