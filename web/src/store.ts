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

// --------------------------------------------------------------------------- //
// Session persistence — lets a reconnect survive a reload / app restart.
// --------------------------------------------------------------------------- //

const SESSION_KEY = "rami.session";

function persist(s: Session): void {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(s));
  } catch {
    /* storage unavailable — ignore */
  }
}

function clearPersisted(): void {
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch {
    /* ignore */
  }
}

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    const s = raw ? JSON.parse(raw) : null;
    if (s && typeof s.code === "string" && typeof s.token === "string" && typeof s.you === "number") {
      return s as Session;
    }
  } catch {
    /* ignore */
  }
  return null;
}

// --------------------------------------------------------------------------- //
// WebSocket with automatic reconnection.
// --------------------------------------------------------------------------- //

let socket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let deliberate = false; // true while we are intentionally leaving
let attempt = 0; // reconnect backoff counter
let logCounter = 0;
let errorTimer: ReturnType<typeof setTimeout> | null = null;

function detach(s: WebSocket): void {
  s.onopen = s.onclose = s.onmessage = s.onerror = null;
}

function openSocket(): void {
  const session = useStore.getState().session;
  if (!session) return;
  if (socket) {
    detach(socket);
    socket.close();
  }
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(`${proto}//${location.host}/ws/table/${session.code}?token=${session.token}`);
  socket.onopen = () => {
    attempt = 0;
    useStore.setState({ connected: true });
  };
  socket.onclose = (ev) => {
    useStore.setState({ connected: false });
    if (deliberate) return;
    if (ev.code === 4404 || ev.code === 4401) {
      // Table gone or token no longer valid — stop trying, drop back to home.
      clearPersisted();
      useStore.setState({ session: null, snapshot: null });
      return;
    }
    scheduleReconnect();
  };
  socket.onmessage = handleMessage;
}

function scheduleReconnect(): void {
  if (reconnectTimer) return;
  const delay = Math.min(1000 * 2 ** attempt, 10_000);
  attempt += 1;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    openSocket();
  }, delay);
}

/** Reconnect immediately when the app returns to the foreground or the network
 * comes back — the standby case that a slow backoff would otherwise miss. */
function reconnectNow(): void {
  if (!useStore.getState().session) return;
  if (socket && socket.readyState === WebSocket.OPEN) return;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  attempt = 0;
  openSocket();
}

if (typeof window !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") reconnectNow();
  });
  window.addEventListener("online", reconnectNow);
}

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

function handleMessage(ev: MessageEvent): void {
  const msg = JSON.parse(ev.data) as ServerMessage;
  if (msg.type === "snapshot") {
    const handIds = msg.your_hand.map((c) => c.id);
    const handSet = new Set(handIds);
    useStore.setState((st) => ({
      snapshot: msg,
      selected: st.selected.filter((id) => handSet.has(id)),
      handOrder: reconcileHandOrder(st.handOrder, handIds),
      tray: st.tray
        .map((g) => ({ ...g, card_ids: g.card_ids.filter((id) => handSet.has(id)) }))
        .filter((g) => g.card_ids.length > 0),
    }));
  } else if (msg.type === "events") {
    const snap = useStore.getState().snapshot;
    const lines = msg.events
      .map((e) => describe(snap, e.type, e.data))
      .filter((text): text is string => text !== null)
      .map((text) => ({ id: ++logCounter, text }));
    if (lines.length) useStore.setState((st) => ({ log: [...lines.reverse(), ...st.log].slice(0, 40) }));
  } else if (msg.type === "error") {
    if (errorTimer) clearTimeout(errorTimer);
    useStore.setState({ error: errorLabel(msg.code) });
    errorTimer = setTimeout(() => useStore.setState({ error: null }), 4000);
  }
}

export const useStore = create<StoreState>((set) => ({
  session: null,
  snapshot: null,
  connected: false,
  error: null,
  log: [],
  selected: [],
  tray: [],
  handOrder: [],

  enter: (session) => {
    deliberate = false;
    attempt = 0;
    persist(session);
    set({ session, snapshot: null, log: [], selected: [], tray: [], handOrder: [] });
    openSocket();
  },

  leave: () => {
    deliberate = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (socket) {
      detach(socket);
      socket.close();
      socket = null;
    }
    clearPersisted();
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
