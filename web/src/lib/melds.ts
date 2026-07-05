// Client-side meld detection + run ordering. Mirrors the server rules
// (src/rami/game/melds.py) closely enough to auto-detect the kind and pre-order
// a run for the tray preview; the server stays authoritative.

import type { CardView, MeldKind } from "../types";

const RANK_ACE = 1;
const RANK_ACE_HIGH = 14;
const MIN_RANK = 1;

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
