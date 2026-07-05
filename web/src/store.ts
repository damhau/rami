import { create } from "zustand";
import type { ClientMessage, MeldKind, ServerMessage, Snapshot } from "./types";
import { t, errorLabel } from "./i18n";

export interface Session {
  code: string;
  token: string;
  you: number;
}

export interface LogLine {
  id: number;
  text: string;
}

export interface TrayGroup {
  kind: MeldKind;
  card_ids: number[];
}

interface StoreState {
  session: Session | null;
  snapshot: Snapshot | null;
  connected: boolean;
  error: string | null;
  log: LogLine[];
  selected: number[];
  tray: TrayGroup[];
  handOrder: number[];

  enter: (session: Session) => void;
  leave: () => void;
  send: (msg: ClientMessage) => void;
  toggleSelect: (id: number) => void;
  clearSelection: () => void;
  addTrayGroup: (group: TrayGroup) => void;
  clearTray: () => void;
  setHandOrder: (ids: number[]) => void;
  dismissError: () => void;
}

let socket: WebSocket | null = null;
let logCounter = 0;
let errorTimer: ReturnType<typeof setTimeout> | null = null;

function seatName(snap: Snapshot | null, seat: number): string {
  return snap?.players.find((p) => p.seat === seat)?.name ?? `Seat ${seat}`;
}

function describe(snap: Snapshot | null, type: string, data: Record<string, unknown>): string | null {
  const who = (s: unknown) => seatName(snap, s as number);
  switch (type) {
    case "round_started":
      return t.event.roundStarted(data.round_no as number);
    case "drew":
      return data.source === "discard"
        ? t.event.tookDiscard(who(data.seat))
        : t.event.drewStock(who(data.seat));
    case "free_card_claimed":
      return t.event.freeClaimed(who(data.seat));
    case "free_card_passed":
      return t.event.freePassed(who(data.seat));
    case "went_out":
      return t.event.wentOut(who(data.seat));
    case "melded":
      return t.event.melded(who(data.seat));
    case "laid_off":
      return t.event.laidOff(who(data.seat));
    case "recovered_joker":
      return t.event.recoveredJoker(who(data.seat));
    case "discarded":
      return t.event.discarded(who(data.seat));
    case "returned_discard":
      return t.event.returnedDiscard(who(data.seat));
    case "round_over":
      return t.event.roundOver(data.round_no as number, who(data.winner_seat));
    case "game_over":
      return t.event.gameOver;
    default:
      return null;
  }
}

/** Keep the player's chosen hand order stable across snapshots: retain the order
 * for cards still in hand, append newly-drawn cards at the end. */
function reconcileHandOrder(prev: number[], handIds: number[]): number[] {
  const present = new Set(handIds);
  const kept = prev.filter((id) => present.has(id));
  const keptSet = new Set(kept);
  const added = handIds.filter((id) => !keptSet.has(id));
  return [...kept, ...added];
}

export const useStore = create<StoreState>((set, get) => ({
  session: null,
  snapshot: null,
  connected: false,
  error: null,
  log: [],
  selected: [],
  tray: [],
  handOrder: [],

  enter: (session) => {
    set({ session, snapshot: null, log: [], selected: [], tray: [], handOrder: [] });
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}/ws/table/${session.code}?token=${session.token}`;
    socket?.close();
    socket = new WebSocket(url);
    socket.onopen = () => set({ connected: true });
    socket.onclose = () => set({ connected: false });
    socket.onmessage = (ev) => {
      const msg = JSON.parse(ev.data) as ServerMessage;
      if (msg.type === "snapshot") {
        const handIds = msg.your_hand.map((c) => c.id);
        const handSet = new Set(handIds);
        set((st) => ({
          snapshot: msg,
          selected: st.selected.filter((id) => handSet.has(id)),
          handOrder: reconcileHandOrder(st.handOrder, handIds),
          tray: st.tray
            .map((g) => ({ ...g, card_ids: g.card_ids.filter((id) => handSet.has(id)) }))
            .filter((g) => g.card_ids.length > 0),
        }));
      } else if (msg.type === "events") {
        const snap = get().snapshot;
        const lines = msg.events
          .map((e) => describe(snap, e.type, e.data))
          .filter((text): text is string => text !== null)
          .map((text) => ({ id: ++logCounter, text }));
        if (lines.length) set((st) => ({ log: [...lines.reverse(), ...st.log].slice(0, 40) }));
      } else if (msg.type === "error") {
        if (errorTimer) clearTimeout(errorTimer);
        set({ error: errorLabel(msg.code) });
        errorTimer = setTimeout(() => set({ error: null }), 4000);
      }
    };
  },

  leave: () => {
    socket?.close();
    socket = null;
    set({
      session: null,
      snapshot: null,
      connected: false,
      selected: [],
      tray: [],
      handOrder: [],
      log: [],
    });
  },

  send: (msg) => {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(msg));
  },

  toggleSelect: (id) =>
    set((st) => ({
      selected: st.selected.includes(id)
        ? st.selected.filter((x) => x !== id)
        : [...st.selected, id],
    })),

  clearSelection: () => set({ selected: [] }),

  addTrayGroup: (group) => set((st) => ({ tray: [...st.tray, group], selected: [] })),

  clearTray: () => set({ tray: [] }),

  setHandOrder: (ids) => set({ handOrder: ids }),

  dismissError: () => set({ error: null }),
}));
