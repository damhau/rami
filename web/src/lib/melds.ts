// Client-side meld detection + run ordering. Mirrors the server rules
// (src/rami/game/melds.py) closely enough to auto-detect the kind and pre-order
// a run for the tray preview; the server stays authoritative.

import type { CardView, MeldKind } from "../types";

const RANK_ACE = 1;
const RANK_ACE_HIGH = 14;
const MIN_RANK = 1;

// Point value of each rank (mirrors src/rami/game/cards.py RANK_POINTS).
const RANK_POINTS: Record<number, number> = {
  1: 11, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9, 10: 10, 11: 10, 12: 10, 13: 10,
};

function rankPoints(rank: number): number {
  return RANK_POINTS[rank === RANK_ACE_HIGH ? RANK_ACE : rank];
}

/** The run's start rank if `cards` are already in a valid left-to-right order,
 * else null. Mirrors the server's _run_start so the tray honours a player's
 * chosen joker placement instead of re-lowering it. */
function runStartInOrder(cards: CardView[]): number | null {
  const reals = cards.filter((c) => !c.is_joker);
  if (reals.length === 0) return null;
  if (new Set(reals.map((c) => c.suit)).size !== 1) return null;
  let candidates: number[] | null = null;
  for (let i = 0; i < cards.length; i++) {
    const c = cards[i];
    if (c.is_joker) continue;
    const opts = c.rank === RANK_ACE ? [RANK_ACE - i, RANK_ACE_HIGH - i] : [c.rank! - i];
    candidates = candidates === null ? opts : candidates.filter((x) => opts.includes(x));
  }
  if (candidates === null || candidates.length === 0) return null;
  const n = cards.length;
  const valid = candidates.filter((s) => {
    const end = s + n - 1;
    if (s < MIN_RANK || end > RANK_ACE_HIGH) return false;
    return !(s === MIN_RANK && end === RANK_ACE_HIGH);
  });
  return valid.length ? Math.min(...valid) : null;
}

/** Laid value of a staged meld: a joker counts as the card it represents.
 * Mirrors the server's meld_points so the tray total matches the go-out check. */
export function meldPoints(kind: MeldKind, cards: CardView[]): number {
  if (kind === "run") {
    // Respect the chosen order when it is a valid run (matches the server), so a
    // joker placed on the high end is valued there, not re-lowered.
    const start = runStartInOrder(cards);
    if (start !== null) {
      return cards.reduce((sum, c, i) => sum + rankPoints(c.is_joker ? start + i : c.rank!), 0);
    }
    const ordered = arrangeRun(cards);
    if (!ordered) return 0;
    const byId = new Map(cards.map((c) => [c.id, c]));
    const seq = ordered.map((id) => byId.get(id)!);
    const anchor = seq.findIndex((c) => !c.is_joker);
    if (anchor === -1) return 0;
    const base = seq[anchor].rank! - anchor; // rank of position 0
    return seq.reduce((sum, c, i) => sum + rankPoints(c.is_joker ? base + i : c.rank!), 0);
  }
  // Set: every card (joker included) is worth the shared rank.
  const rank = cards.find((c) => !c.is_joker)?.rank;
  if (rank == null) return 0;
  return cards.reduce((sum, c) => sum + rankPoints(c.is_joker ? rank : c.rank!), 0);
}

/** Order `cards` into a valid run (any input order), or null. Returns card ids. */
export function arrangeRun(cards: CardView[]): number[] | null {
  if (cards.length < 3) return null;
  const reals = cards.filter((c) => !c.is_joker);
  const jokers = cards.filter((c) => c.is_joker);
  if (reals.length === 0) return null;

  const suits = new Set(reals.map((c) => c.suit));
  if (suits.size !== 1) return null;

  const n = cards.length;
  const aces = reals.filter((c) => c.rank === RANK_ACE);
  const fixed = reals.filter((c) => c.rank !== RANK_ACE);

  for (let hiMask = 0; hiMask < 2 ** aces.length; hiMask++) {
    const byRank = new Map<number, CardView>();
    let collision = false;
    for (const c of fixed) {
      if (byRank.has(c.rank!)) {
        collision = true;
        break;
      }
      byRank.set(c.rank!, c);
    }
    for (let i = 0; i < aces.length && !collision; i++) {
      const rank = (hiMask >> i) & 1 ? RANK_ACE_HIGH : RANK_ACE;
      if (byRank.has(rank)) {
        collision = true;
        break;
      }
      byRank.set(rank, aces[i]);
    }
    if (collision) continue;

    const ranks = [...byRank.keys()].sort((a, b) => a - b);
    const lo = ranks[0];
    const hi = ranks[ranks.length - 1];
    const startMin = Math.max(MIN_RANK, hi - n + 1);
    const startMax = Math.min(lo, RANK_ACE_HIGH - n + 1);
    for (let start = startMin; start <= startMax; start++) {
      const end = start + n - 1;
      if (start === MIN_RANK && end === RANK_ACE_HIGH) continue; // no full circle
      const seq: number[] = [];
      const spare = [...jokers];
      let ok = true;
      for (let rank = start; rank <= end; rank++) {
        const real = byRank.get(rank);
        if (real) seq.push(real.id);
        else if (spare.length) seq.push(spare.shift()!.id);
        else {
          ok = false;
          break;
        }
      }
      if (ok && spare.length === 0) return seq;
    }
  }
  return null;
}

/** Infer the meld kind from a selection and return ordered ids, or null. */
export function detectMeld(cards: CardView[]): { kind: MeldKind; card_ids: number[] } | null {
  if (cards.length < 3) return null;
  const reals = cards.filter((c) => !c.is_joker);
  if (reals.length === 0) return null;

  // Same rank among all real cards -> a set (order is irrelevant).
  if (new Set(reals.map((c) => c.rank)).size === 1) {
    return { kind: "set", card_ids: cards.map((c) => c.id) };
  }
  const run = arrangeRun(cards);
  if (run) return { kind: "run", card_ids: run };
  return null;
}

/** One way to lay the selection as a run: the ordered ids plus, for each joker,
 * the rank it would represent — so the player can choose where jokers sit (#2). */
export interface RunOption {
  card_ids: number[];
  ranks: number[]; // rank at each position (for jokers, the value they stand in for)
  jokerRanks: Record<number, number>; // joker id -> represented rank
}

/** True if every real card shares a rank, so the selection can be a set (#9). */
export function canBeSet(cards: CardView[]): boolean {
  if (cards.length < 3) return false;
  const reals = cards.filter((c) => !c.is_joker);
  return reals.length > 0 && new Set(reals.map((c) => c.rank)).size === 1;
}

/** Every distinct valid run ordering for `cards`, one per achievable rank window
 * (mirrors arrangeRun but collects all starts instead of the lowest). */
export function runOptions(cards: CardView[]): RunOption[] {
  if (cards.length < 3) return [];
  const reals = cards.filter((c) => !c.is_joker);
  const jokers = cards.filter((c) => c.is_joker);
  if (reals.length === 0) return [];
  if (new Set(reals.map((c) => c.suit)).size !== 1) return [];

  const n = cards.length;
  const aces = reals.filter((c) => c.rank === RANK_ACE);
  const fixed = reals.filter((c) => c.rank !== RANK_ACE);

  const seen = new Set<string>();
  const out: RunOption[] = [];

  for (let hiMask = 0; hiMask < 2 ** aces.length; hiMask++) {
    const byRank = new Map<number, CardView>();
    let collision = false;
    for (const c of fixed) {
      if (byRank.has(c.rank!)) {
        collision = true;
        break;
      }
      byRank.set(c.rank!, c);
    }
    for (let i = 0; i < aces.length && !collision; i++) {
      const rank = (hiMask >> i) & 1 ? RANK_ACE_HIGH : RANK_ACE;
      if (byRank.has(rank)) {
        collision = true;
        break;
      }
      byRank.set(rank, aces[i]);
    }
    if (collision) continue;

    const ranks = [...byRank.keys()].sort((a, b) => a - b);
    const lo = ranks[0];
    const hi = ranks[ranks.length - 1];
    const startMin = Math.max(MIN_RANK, hi - n + 1);
    const startMax = Math.min(lo, RANK_ACE_HIGH - n + 1);
    for (let start = startMin; start <= startMax; start++) {
      const end = start + n - 1;
      if (start === MIN_RANK && end === RANK_ACE_HIGH) continue; // no full circle
      const key = `${start}-${end}`;
      if (seen.has(key)) continue;
      const seq: number[] = [];
      const posRanks: number[] = [];
      const jokerRanks: Record<number, number> = {};
      const spare = [...jokers];
      let ok = true;
      for (let rank = start; rank <= end; rank++) {
        const real = byRank.get(rank);
        posRanks.push(rank);
        if (real) seq.push(real.id);
        else if (spare.length) {
          const j = spare.shift()!;
          seq.push(j.id);
          jokerRanks[j.id] = rank;
        } else {
          ok = false;
          break;
        }
      }
      if (!ok || spare.length) continue;
      seen.add(key);
      out.push({ card_ids: seq, ranks: posRanks, jokerRanks });
    }
  }
  out.sort((a, b) => a.ranks[0] - b.ranks[0]);
  return out;
}

/** For laying a single joker onto an existing run: the ranks it can represent
 * (the two ends), so the player can extend high or low (#11). */
export function jokerRunLayOffRanks(meldRanks: number[]): number[] {
  if (meldRanks.length === 0) return [];
  const sorted = [...meldRanks].sort((a, b) => a - b);
  const start = sorted[0];
  const end = sorted[sorted.length - 1];
  const opts: number[] = [];
  if (start - 1 >= MIN_RANK && !(start - 1 === MIN_RANK && end === RANK_ACE_HIGH)) {
    opts.push(start - 1);
  }
  if (end + 1 <= RANK_ACE_HIGH && !(start === MIN_RANK && end + 1 === RANK_ACE_HIGH)) {
    opts.push(end + 1);
  }
  return opts;
}
