import { useState } from "react";
import {
  DndContext,
  MouseSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { CardView, MeldView, Snapshot } from "../types";
import { useStore } from "../store";
import { t, contractLabel, meldKindLabel } from "../i18n";
import { detectMeld, meldPoints } from "../lib/melds";
import { Button } from "./ui/button";
import { CardBack, PlayingCard } from "./PlayingCard";
import { cn } from "../lib/utils";

/** One hand card wired for drag-to-reorder while still handling tap-to-select. */
function SortableCard({
  card,
  selected,
  onClick,
  overlap,
}: {
  card: CardView;
  selected: boolean;
  onClick: () => void;
  overlap: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: card.id,
  });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 40 : undefined,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      // select-none + draggable=false stop Firefox from starting a native
      // text/image drag that would pre-empt dnd-kit's pointer drag.
      draggable={false}
      // touch-none lets dnd-kit's touch sensor receive the drag instead of the
      // browser hijacking it as a scroll (the hand wraps, so no scroll is lost).
      className={cn(overlap && "sm:-ml-3", "touch-none select-none")}
      {...attributes}
      {...listeners}
    >
      <PlayingCard card={card} selected={selected} onClick={onClick} />
    </div>
  );
}

export function GameTable({ snap }: { snap: Snapshot }) {
  const { selected, tray, send, toggleSelect, addTrayGroup, clearTray, handOrder, setHandOrder } =
    useStore();
  const [meldHint, setMeldHint] = useState<string | null>(null);
  const me = snap.you;
  const mine = snap.players[me];
  const opponents = snap.players.filter((p) => p.seat !== me);

  // Mouse: drag after a small move (a click still selects). Touch: press-and-hold
  // to drag, so a quick swipe still scrolls the hand strip on a phone.
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 8 } }),
  );

  const isMyTurn = mine?.is_turn ?? false;
  const canDraw = snap.phase === "await_draw" && isMyTurn;
  const canAct = snap.phase === "await_discard" && isMyTurn;
  const goneOut = mine?.has_gone_out ?? false;
  // The free-card offer is independent of the drawer's turn: it is shown whenever
  // this seat is the one currently being offered the refused discard.
  const freeForMe = snap.free_card?.current_seat === me;
  const mustLayTaken = snap.taken_from_discard_id !== null;

  const layOffMode = canAct && goneOut && selected.length === 1;

  // Cards already staged in the tray are hidden from the hand until laid/cleared.
  const stagedIds = new Set(tray.flatMap((g) => g.card_ids));
  const trayTotal = tray.reduce((sum, g) => {
    const cards = g.card_ids
      .map((id) => snap.your_hand.find((c) => c.id === id))
      .filter((c): c is CardView => c !== undefined);
    return sum + meldPoints(g.kind, cards);
  }, 0);
  const enoughToGoOut = trayTotal >= snap.go_out_min_points;

  // Hand ordered by the player's drag-arranged order (reconciled in the store).
  const orderedHand = handOrder
    .map((id) => snap.your_hand.find((c) => c.id === id))
    .filter((c): c is CardView => c !== undefined);
  const fullHand = orderedHand.length === snap.your_hand.length ? orderedHand : snap.your_hand;
  const hand = fullHand.filter((c) => !stagedIds.has(c.id));

  const onDragEnd = (ev: DragEndEvent) => {
    const { active, over } = ev;
    if (!over || active.id === over.id) return;
    // Reorder within the full hand order so staged (hidden) cards keep their place.
    const from = handOrder.indexOf(active.id as number);
    const to = handOrder.indexOf(over.id as number);
    if (from !== -1 && to !== -1) setHandOrder(arrayMove(handOrder, from, to));
  };

  const layOff = (meld: MeldView) => {
    if (layOffMode) send({ type: "lay_off", meld_id: meld.id, card_id: selected[0] });
  };
  const recoverJoker = (meld: MeldView) => {
    if (canAct && goneOut && selected.length === 1)
      send({ type: "recover_joker", meld_id: meld.id, card_id: selected[0] });
  };

  const addMeld = () => {
    const cards = selected
      .map((id) => snap.your_hand.find((c) => c.id === id))
      .filter((c): c is CardView => c !== undefined);
    const detected = detectMeld(cards);
    if (!detected) {
      setMeldHint(cards.length < 3 ? t.game.tooFewCards : t.game.notAMeld);
      return;
    }
    setMeldHint(null);
    addTrayGroup(detected);
  };

  const layDown = () => {
    if (tray.length) send({ type: "lay_melds", melds: tray });
  };
  const discard = () => {
    if (selected.length === 1) send({ type: "discard", card_id: selected[0] });
  };

  // Who is acting right now (the free-card decider, else the turn player).
  const activeSeat = snap.free_card ? snap.free_card.current_seat : snap.turn_seat;
  const activeIsMe = activeSeat === me;
  const activeName = snap.players.find((p) => p.seat === activeSeat)?.name ?? "";
  const turnLabel = activeIsMe ? t.game.yourTurnShort : activeName;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {/* ---------------- felt (scrolls if taller than the available space) ---------------- */}
      <div className="min-h-0 flex-1 overflow-y-auto">
      {/* pb-20 keeps the felt's flowing content (melds) clear of the absolute
          status pill and free-card prompt pinned near the bottom. */}
      {/* On phones the mat is only as tall as its content (so it doesn't dominate
          the screen); on sm+ it fills the space to read as a full table. */}
      <div className="felt relative overflow-hidden rounded-3xl px-3 pt-3 pb-4 sm:min-h-full sm:px-4 sm:pt-4 sm:pb-6 md:px-6 md:pt-6">
        {/* top bar: whose turn (left) + contract (right) */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1.5 rounded-full border border-white/10 bg-ink/60 px-2.5 py-1 text-[11px] backdrop-blur sm:text-xs">
            <span
              className={cn(
                "h-1.5 w-1.5 shrink-0 rounded-full",
                activeIsMe ? "animate-pulse bg-gold" : "bg-slate-400",
              )}
            />
            <span className={cn("truncate", activeIsMe ? "font-semibold text-gold" : "text-slate-200")}>
              {turnLabel}
            </span>
          </div>
          <div className="flex min-w-0 items-center gap-2 rounded-full border border-gold/30 bg-ink/60 px-3 py-1 backdrop-blur">
            <span className="shrink-0 rounded-full bg-gold/15 px-1.5 py-0.5 text-[10px] font-semibold text-gold sm:text-[11px]">
              {t.game.round(snap.round_no)}
            </span>
            <span className="truncate text-[11px] font-semibold sm:text-sm">
              {snap.contract ? contractLabel(snap.contract.requirements) : "—"}
            </span>
            <span className="hidden h-3 w-px shrink-0 bg-white/15 sm:block" />
            <span className="hidden shrink-0 text-[10px] text-slate-300 sm:inline sm:text-[11px]">
              ≥ <b className="text-white">{snap.go_out_min_points} pts</b>
            </span>
          </div>
        </div>

        {/* opponents */}
        <div className="mt-3 flex flex-wrap items-start justify-center gap-3 sm:mt-5 sm:gap-4 md:mt-6 md:gap-8">
          {opponents.map((p) => (
            <div key={p.seat} className="flex flex-col items-center">
              <div
                className={cn(
                  "flex items-center gap-2 rounded-xl bg-ink/55 px-3 py-2",
                  p.is_turn && "turn-glow",
                )}
              >
                <span className="grid h-9 w-9 place-items-center rounded-full bg-sky-500/25 font-bold text-sky-200">
                  {p.name.charAt(0).toUpperCase()}
                </span>
                <div className="leading-tight">
                  <div className="text-sm font-semibold">
                    {p.name}
                    {!p.is_bot && !p.connected && (
                      <span className="ml-1 text-[10px] text-rose-300">{t.game.offline}</span>
                    )}
                  </div>
                  <div className="text-[11px] text-slate-300">
                    {p.is_turn ? (
                      <span className="text-gold">{t.game.theirTurn}</span>
                    ) : p.has_gone_out ? (
                      <span className="text-emerald-300">{t.game.wentOut}</span>
                    ) : (
                      <span>{t.game.cards(p.hand_count)}</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="mt-2 hidden sm:flex">
                {Array.from({ length: Math.min(p.hand_count, 7) }).map((_, i) => (
                  <div key={i} className={i ? "-ml-7" : ""}>
                    <CardBack size="sm" />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* center: stock + discard */}
        <div className="mt-3 flex items-center justify-center gap-6 sm:mt-6 md:mt-8 md:gap-8">
          <div className="flex flex-col items-center gap-1">
            <button
              disabled={!canDraw}
              onClick={() => send({ type: "draw_stock" })}
              className={cn("relative", canDraw && "cursor-pointer")}
              title={t.game.drawTitle}
            >
              <CardBack size="md" />
              {canDraw && <span className="absolute -inset-1 rounded-[11px] ring-2 ring-gold/70" />}
            </button>
            <span className="rounded-full bg-ink/60 px-2 py-0.5 text-[11px] text-slate-300">
              {t.game.stock(snap.stock_count)}
            </span>
          </div>

          <div className="flex flex-col items-center gap-1">
            <button
              disabled={!canDraw || !snap.discard_top}
              onClick={() => send({ type: "draw_discard" })}
              className={cn(canDraw && snap.discard_top && "cursor-pointer")}
              title={t.game.takeDiscardTitle}
            >
              {snap.discard_top ? (
                <div className={cn("rounded-xl", canDraw && "ring-2 ring-gold/50 ring-offset-2 ring-offset-felt")}>
                  <PlayingCard card={snap.discard_top} />
                </div>
              ) : (
                <div className="grid h-[72px] w-[50px] place-items-center rounded-[9px] border border-dashed border-white/20 text-xs text-white/40 md:h-[92px] md:w-[64px]">
                  {t.game.empty}
                </div>
              )}
            </button>
            <span className="rounded-full bg-ink/60 px-2 py-0.5 text-[11px] text-slate-300">
              {t.game.discardPile}
            </span>
          </div>
        </div>

        {/* table melds — only shown once something is on the table */}
        {snap.table_melds.length > 0 && (
        <div className="mt-4 md:mt-8">
          {layOffMode && (
            <div className="mb-2 text-center text-[11px] uppercase tracking-wider text-gold">
              {t.game.clickToLayOff}
            </div>
          )}
          <div className="flex flex-wrap items-start justify-center gap-3">
            {snap.table_melds.map((meld) => {
              const hasJoker = meld.cards.some((c) => c.is_joker);
              const owner = snap.players.find((p) => p.seat === meld.owner_seat)?.name;
              return (
                <div
                  key={meld.id}
                  onClick={() => layOff(meld)}
                  className={cn(
                    "rounded-xl bg-black/15 p-2",
                    layOffMode && "cursor-pointer ring-1 ring-gold/40 hover:ring-gold",
                  )}
                >
                  <div className="flex">
                    {meld.cards.map((c, i) => (
                      <div key={c.id} className={i ? "-ml-4" : ""}>
                        <PlayingCard card={c} size="sm" repLabel={meld.reprs[c.id]?.label} />
                      </div>
                    ))}
                  </div>
                  <div className="mt-1 flex items-center justify-center gap-2 text-[11px] text-slate-400">
                    <span>
                      {owner} · {meldKindLabel(meld.kind, meld.cards.length)} · {meld.points} pts
                    </span>
                    {hasJoker && canAct && goneOut && selected.length === 1 && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          recoverJoker(meld);
                        }}
                        className="rounded bg-gold/15 px-1.5 py-0.5 text-gold hover:bg-gold/25"
                      >
                        ↩ joker
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        )}

        {/* free-card prompt */}
        {freeForMe && (
          <div className="absolute inset-x-0 bottom-16 flex justify-center">
            <div className="flex items-center gap-3 rounded-xl border border-gold/40 bg-ink/90 px-4 py-2.5 shadow-2xl">
              <span className="text-sm">
                {(() => {
                  const [pre, label, post] = t.game.freePrompt(snap.discard_top?.label ?? "");
                  return (
                    <>
                      {pre}
                      <b>{label}</b>
                      {post}
                    </>
                  );
                })()}
              </span>
              <Button size="sm" onClick={() => send({ type: "claim_free_card" })}>
                {t.game.claim}
              </Button>
              <Button size="sm" variant="outline" onClick={() => send({ type: "pass_free_card" })}>
                {t.game.pass}
              </Button>
            </div>
          </div>
        )}

      </div>
      </div>

      {/* ---------------- player dock (pinned; hand + actions always reachable) ---------------- */}
      <div
        className="shrink-0 rounded-2xl border border-white/10 bg-white/[0.04] p-3 md:p-4"
        style={{ paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))" }}
      >
        {mustLayTaken && (
          <div className="mb-3 flex flex-wrap items-center gap-3 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-sm text-amber-200">
            <span className="min-w-0 flex-1">{t.game.mustLayTaken}</span>
            <Button
              size="sm"
              variant="outline"
              className="shrink-0"
              onClick={() => send({ type: "return_discard" })}
            >
              {t.game.cancelPickup}
            </Button>
          </div>
        )}

        {/* meld tray */}
        {(tray.length > 0 || (canAct && selected.length >= 3)) && (
          <div className="mb-3 flex flex-wrap items-center gap-3 rounded-xl border border-gold/25 bg-ink/40 p-3">
            <span className="rounded-full bg-gold/15 px-2 py-0.5 text-[11px] font-semibold text-gold">
              {t.game.tray}
            </span>
            {tray.length > 0 && (
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                  enoughToGoOut
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "bg-white/10 text-slate-300",
                )}
                title={goneOut ? undefined : enoughToGoOut ? t.game.enoughToGoOut : t.game.needMore(snap.go_out_min_points)}
              >
                {t.game.trayTotal(trayTotal)}
                {!goneOut && (enoughToGoOut ? ` · ${t.game.enoughToGoOut}` : ` · ${t.game.needMore(snap.go_out_min_points)}`)}
              </span>
            )}
            {tray.map((g, gi) => (
              <div key={gi} className="flex items-center gap-1 rounded-lg bg-black/20 p-1.5">
                {g.card_ids.map((id) => {
                  const card = snap.your_hand.find((h) => h.id === id);
                  return card ? <PlayingCard key={id} card={card} size="xs" /> : null;
                })}
                <span className="px-1 text-[10px] uppercase text-slate-400">
                  {meldKindLabel(g.kind, g.card_ids.length)}
                </span>
              </div>
            ))}
            {tray.length === 0 && (
              <span className="text-sm text-slate-300">{t.game.selectedHint(selected.length)}</span>
            )}
            <div className="ml-auto flex gap-2">
              {tray.length > 0 && (
                <Button size="sm" variant="ghost" onClick={clearTray}>
                  {t.game.clear}
                </Button>
              )}
              <Button size="sm" onClick={layDown} disabled={tray.length === 0}>
                {goneOut ? t.game.layDown : t.game.goOut} {tray.length > 0 ? `(${tray.length})` : ""}
              </Button>
            </div>
          </div>
        )}

        {meldHint && <div className="mb-2 text-sm text-rose-300">{meldHint}</div>}

        {/* hand — pt-6 gives headroom so a selected/hovered card's upward
            lift (translateY -16px) isn't clipped: overflow-x-auto forces
            overflow-y to clip too, so the scroll box needs top padding. */}
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={hand.map((c) => c.id)} strategy={rectSortingStrategy}>
            {/* Phones: wrap to as many rows as needed so the whole hand is
                visible without horizontal scrolling. Desktop: one fanned row. */}
            <div className="mt-3 flex flex-wrap items-end justify-center gap-x-1 gap-y-3 pt-6 pb-2 sm:flex-nowrap sm:justify-start sm:gap-0 sm:overflow-x-auto">
              {hand.map((c, i) => (
                <SortableCard
                  key={c.id}
                  card={c}
                  overlap={i > 0}
                  selected={selected.includes(c.id)}
                  onClick={() => toggleSelect(c.id)}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>

        {/* actions — one compact row on phones, wraps to full labels on sm+ */}
        <div className="mt-3 flex items-center gap-1.5 sm:flex-wrap sm:gap-2">
          <Button
            size="sm"
            className="min-w-0 flex-1 text-xs sm:flex-none sm:text-sm"
            disabled={!canDraw}
            onClick={() => send({ type: "draw_stock" })}
          >
            {t.game.draw}
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="min-w-0 flex-1 text-xs sm:flex-none sm:text-sm"
            disabled={!canDraw || !snap.discard_top}
            onClick={() => send({ type: "draw_discard" })}
          >
            <span className="sm:hidden">{t.game.takeShort}</span>
            <span className="hidden sm:inline">
              {t.game.takeDiscard} {snap.discard_top ? `(${snap.discard_top.label})` : ""}
            </span>
          </Button>
          <span className="mx-1 hidden h-6 w-px bg-white/10 sm:block" />
          <Button
            size="sm"
            variant="outline"
            className="min-w-0 flex-1 text-xs sm:flex-none sm:text-sm"
            disabled={!canAct || selected.length < 3}
            onClick={addMeld}
          >
            <span className="sm:hidden">{t.game.addShort}</span>
            <span className="hidden sm:inline">{t.game.addMeld}</span>
          </Button>
          <Button
            size="sm"
            variant="destructive"
            className="min-w-0 flex-1 text-xs sm:ml-auto sm:flex-none sm:text-sm"
            disabled={!canAct || selected.length !== 1 || mustLayTaken}
            onClick={discard}
          >
            {t.game.discard}
          </Button>
        </div>
      </div>
    </div>
  );
}
