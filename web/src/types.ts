// Wire types mirroring src/rami/realtime/protocol.py

export type Suit = "S" | "H" | "D" | "C";
export type MeldKind = "set" | "run";
export type Phase =
  | "lobby"
  | "await_draw"
  | "await_discard"
  | "free_card"
  | "round_over"
  | "game_over";

export interface CardView {
  id: number;
  suit: Suit | null;
  rank: number | null;
  is_joker: boolean;
  label: string;
}

export interface ReprView {
  suit: Suit;
  rank: number;
  label: string;
}

export interface MeldView {
  id: number;
  kind: MeldKind;
  owner_seat: number;
  cards: CardView[];
  reprs: Record<number, ReprView>;
  points: number;
}

export interface ReqView {
  kind: MeldKind;
  min_len: number;
}

export interface ContractView {
  round_no: number;
  label: string;
  requirements: ReqView[];
}

export interface PlayerView {
  seat: number;
  name: string;
  has_gone_out: boolean;
  hand_count: number;
  round_score: number;
  total_score: number;
  connected: boolean;
  ready: boolean;
  is_turn: boolean;
}

export interface FreeCardView {
  current_seat: number;
  pending_seats: number[];
}

export interface StandingView {
  seat: number;
  name: string;
  total: number;
}

export interface Snapshot {
  type: "snapshot";
  code: string;
  you: number;
  phase: Phase;
  round_no: number;
  turn_seat: number;
  dealer_seat: number;
  stock_count: number;
  discard_top: CardView | null;
  discard_count: number;
  contract: ContractView | null;
  free_card: FreeCardView | null;
  taken_from_discard_id: number | null;
  go_out_min_points: number;
  players: PlayerView[];
  your_hand: CardView[];
  table_melds: MeldView[];
  last_round_scores: Record<number, number>;
  standings: StandingView[] | null;
}

export interface GameEvent {
  type: string;
  data: Record<string, unknown>;
}

export interface EventsMsg {
  type: "events";
  events: GameEvent[];
}

export interface ErrorMsg {
  type: "error";
  code: string;
  message: string;
}

export type ServerMessage = Snapshot | EventsMsg | ErrorMsg;

// Client -> server
export type ClientMessage =
  | { type: "draw_stock" }
  | { type: "draw_discard" }
  | { type: "claim_free_card" }
  | { type: "pass_free_card" }
  | { type: "lay_melds"; melds: { kind: MeldKind; card_ids: number[] }[] }
  | { type: "lay_off"; meld_id: number; card_id: number }
  | { type: "recover_joker"; meld_id: number; card_id: number }
  | { type: "discard"; card_id: number }
  | { type: "start" }
  | { type: "next_round" }
  | { type: "ready"; ready: boolean };

// REST
export interface SeatInfo {
  seat: number;
  name: string;
  connected: boolean;
  ready: boolean;
}

export interface JoinedTable {
  code: string;
  seat: number;
  token: string;
  host: boolean;
  players: SeatInfo[];
}
