import type { CardView } from "../types";
import { cn } from "../lib/utils";

const SUIT_GLYPH: Record<string, string> = { S: "♠", H: "♥", D: "♦", C: "♣" };

export function rankLabel(rank: number | null): string {
  if (rank === null) return "";
  if (rank === 1 || rank === 14) return "A";
  if (rank === 11) return "J";
  if (rank === 12) return "Q";
  if (rank === 13) return "K";
  return String(rank);
}

export type CardSize = "xs" | "sm" | "md";

interface Props {
  card: CardView;
  size?: CardSize;
  selected?: boolean;
  onClick?: () => void;
  /** Label of the card a joker represents (shown under it on the table). */
  repLabel?: string;
}

export function PlayingCard({ card, size = "md", selected, onClick, repLabel }: Props) {
  const sizeClass = size === "sm" ? "sm" : size === "xs" ? "xs" : "";
  const color = card.suit === "H" || card.suit === "D" ? "red" : "black";

  if (card.is_joker) {
    return (
      <div
        className={cn("pcard joker", sizeClass, onClick && "clickable", selected && "selected")}
        onClick={onClick}
        title="Joker"
      >
        <div className="pip">★</div>
        <span className="absolute inset-x-0 bottom-1 text-center text-[9px] font-semibold text-gold/90">
          {repLabel ? `=${repLabel}` : "JOKER"}
        </span>
      </div>
    );
  }

  const glyph = card.suit ? SUIT_GLYPH[card.suit] : "";
  const rk = rankLabel(card.rank);

  return (
    <div
      className={cn("pcard", sizeClass, onClick && "clickable", selected && "selected")}
      onClick={onClick}
    >
      <div className={cn("corner", color)}>
        <span className="rk">{rk}</span>
        <span>{glyph}</span>
      </div>
      <div className={cn("pip", color)}>{glyph}</div>
      {size === "md" && (
        <div className={cn("corner br", color)}>
          <span className="rk">{rk}</span>
          <span>{glyph}</span>
        </div>
      )}
    </div>
  );
}

export function CardBack({ size = "sm" }: { size?: CardSize }) {
  const sizeClass = size === "sm" ? "sm" : size === "xs" ? "xs" : "";
  return <div className={cn("pcard back", sizeClass)} />;
}
