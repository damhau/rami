import { create } from "zustand";
import type { ClientMessage, MeldKind, ServerMessage, Snapshot } from "./types";

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

  enter: (session: Session) => void;
  leave: () => void;
  send: (msg: ClientMessage) => void;
  toggleSelect: (id: number) => void;
  clearSelection: () => void;
  addTrayGroup: (kind: MeldKind) => void;
  clearTray: () => void;
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
      return `Round ${data.round_no} started.`;
    case "drew":
      return data.source === "discard"
        ? `${who(data.seat)} took the discard.`
        : `${who(data.seat)} drew from the stock.`;
    case "free_card_claimed":
      return `${who(data.seat)} claimed the free card.`;
    case "free_card_passed":
      return `${who(data.seat)} passed on the free card.`;
    case "went_out":
      return `${who(data.seat)} went out!`;
    case "melded":
      return `${who(data.seat)} laid a meld.`;
    case "laid_off":
      return `${who(data.seat)} laid off a card.`;
    case "recovered_joker":
      return `${who(data.seat)} recovered a joker.`;
    case "discarded":
      return `${who(data.seat)} discarded.`;
    case "round_over":
      return `Round ${data.round_no} over — ${who(data.winner_seat)} went out.`;
    case "game_over":
      return `Game over!`;
    default:
      return null;
  }
}

export const useStore = create<StoreState>((set, get) => ({
  session: null,
  snapshot: null,
  connected: false,
  error: null,
  log: [],
  selected: [],
  tray: [],

  enter: (session) => {
    set({ session, snapshot: null, log: [], selected: [], tray: [] });
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}/ws/table/${session.code}?token=${session.token}`;
    socket?.close();
    socket = new WebSocket(url);
    socket.onopen = () => set({ connected: true });
    socket.onclose = () => set({ connected: false });
    socket.onmessage = (ev) => {
      const msg = JSON.parse(ev.data) as ServerMessage;
      if (msg.type === "snapshot") {
        const handIds = new Set(msg.your_hand.map((c) => c.id));
        set((st) => ({
          snapshot: msg,
          selected: st.selected.filter((id) => handIds.has(id)),
          tray: st.tray
            .map((g) => ({ ...g, card_ids: g.card_ids.filter((id) => handIds.has(id)) }))
            .filter((g) => g.card_ids.length > 0),
        }));
      } else if (msg.type === "events") {
        const snap = get().snapshot;
        const lines = msg.events
          .map((e) => describe(snap, e.type, e.data))
          .filter((t): t is string => t !== null)
          .map((text) => ({ id: ++logCounter, text }));
        if (lines.length) set((st) => ({ log: [...lines.reverse(), ...st.log].slice(0, 40) }));
      } else if (msg.type === "error") {
        if (errorTimer) clearTimeout(errorTimer);
        set({ error: msg.message });
        errorTimer = setTimeout(() => set({ error: null }), 4000);
      }
    };
  },

  leave: () => {
    socket?.close();
    socket = null;
    set({ session: null, snapshot: null, connected: false, selected: [], tray: [], log: [] });
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

  addTrayGroup: (kind) =>
    set((st) => {
      if (st.selected.length < 3) return st;
      return {
        tray: [...st.tray, { kind, card_ids: st.selected }],
        selected: [],
      };
    }),

  clearTray: () => set({ tray: [] }),

  dismissError: () => set({ error: null }),
}));
