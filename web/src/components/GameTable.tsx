import type { MeldView, Snapshot } from "../types";
import { useStore } from "../store";
import { Button } from "./ui/button";
import { CardBack, PlayingCard } from "./PlayingCard";
import { cn } from "../lib/utils";

export function GameTable({ snap }: { snap: Snapshot }) {
  const { selected, tray, send, toggleSelect, addTrayGroup, clearTray } = useStore();
  const me = snap.you;
  const mine = snap.players[me];
  const opponents = snap.players.filter((p) => p.seat !== me);

  const isMyTurn = mine?.is_turn ?? false;
  const canDraw = snap.phase === "await_draw" && isMyTurn;
  const canAct = snap.phase === "await_discard" && isMyTurn;
  const goneOut = mine?.has_gone_out ?? false;
  const freeForMe = snap.phase === "free_card" && snap.free_card?.current_seat === me;
  const mustLayTaken = snap.taken_from_discard_id !== null;

  const layOffMode = canAct && goneOut && selected.length === 1;

  const layOff = (meld: MeldView) => {
    if (layOffMode) send({ type: "lay_off", meld_id: meld.id, card_id: selected[0] });
  };
  const recoverJoker = (meld: MeldView) => {
    if (canAct && goneOut && selected.length === 1)
      send({ type: "recover_joker", meld_id: meld.id, card_id: selected[0] });
  };

  const layDown = () => {
    if (tray.length) send({ type: "lay_melds", melds: tray });
  };
  const discard = () => {
    if (selected.length === 1) send({ type: "discard", card_id: selected[0] });
  };

  const statusText = (() => {
    if (snap.phase === "free_card") {
      const who = snap.players.find((p) => p.seat === snap.free_card?.current_seat)?.name;
      return freeForMe ? "A free card is offered to you." : `${who} is deciding on a free card…`;
    }
    if (isMyTurn) return canDraw ? "Your turn — draw a card." : "Your turn — meld and discard.";
    const turn = snap.players.find((p) => p.seat === snap.turn_seat)?.name;
    return `Waiting for ${turn}…`;
  })();

  return (
    <div className="flex flex-col gap-4">
      {/* ---------------- felt ---------------- */}
      <div className="felt relative min-h-[460px] overflow-hidden rounded-3xl p-4 md:min-h-[560px] md:p-6">
        {/* contract banner */}
        <div className="absolute left-1/2 top-3 z-10 -translate-x-1/2">
          <div className="flex flex-wrap items-center justify-center gap-3 rounded-full border border-gold/30 bg-ink/70 px-4 py-1.5 backdrop-blur">
            <span className="rounded-full bg-gold/15 px-2 py-0.5 text-[11px] font-semibold text-gold">
              Round {snap.round_no} / 11
            </span>
            <span className="text-sm font-semibold">Contract: {snap.contract?.label}</span>
            <span className="hidden h-4 w-px bg-white/15 sm:block" />
            <span className="text-[11px] text-slate-300">
              go out with <b className="text-white">≥ {snap.go_out_min_points} pts</b>
            </span>
          </div>
        </div>

        {/* opponents */}
        <div className="mt-12 flex flex-wrap items-start justify-center gap-4 md:mt-14 md:gap-8">
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
                    {!p.connected && <span className="ml-1 text-[10px] text-rose-300">offline</span>}
                  </div>
                  <div className="text-[11px] text-slate-300">
                    {p.is_turn ? (
                      <span className="text-gold">● their turn</span>
                    ) : p.has_gone_out ? (
                      <span className="text-emerald-300">▣ went out</span>
                    ) : (
                      <span>{p.hand_count} cards</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="mt-2 flex">
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
        <div className="mt-6 flex items-center justify-center gap-6 md:mt-8 md:gap-8">
          <div className="flex flex-col items-center gap-1">
            <button
              disabled={!canDraw}
              onClick={() => send({ type: "draw_stock" })}
              className={cn("relative", canDraw && "cursor-pointer")}
              title="Draw from stock"
            >
              <CardBack size="md" />
              {canDraw && (
                <span className="absolute -inset-1 rounded-[11px] ring-2 ring-gold/70" />
              )}
            </button>
            <span className="rounded-full bg-ink/60 px-2 py-0.5 text-[11px] text-slate-300">
              Stock · {snap.stock_count}
            </span>
          </div>

          <div className="flex flex-col items-center gap-1">
            <button
              disabled={!canDraw || !snap.discard_top}
              onClick={() => send({ type: "draw_discard" })}
              className={cn(canDraw && snap.discard_top && "cursor-pointer")}
              title="Take the discard"
            >
              {snap.discard_top ? (
                <div className={cn("rounded-xl", canDraw && "ring-2 ring-gold/50 ring-offset-2 ring-offset-felt")}>
                  <PlayingCard card={snap.discard_top} />
                </div>
              ) : (
                <div className="grid h-[72px] w-[50px] place-items-center rounded-[9px] border border-dashed border-white/20 text-xs text-white/40 md:h-[92px] md:w-[64px]">
                  empty
                </div>
              )}
            </button>
            <span className="rounded-full bg-ink/60 px-2 py-0.5 text-[11px] text-slate-300">
              Discard
            </span>
          </div>
        </div>

        {/* table melds */}
        <div className="mt-6 md:mt-8">
          <div className="mb-2 text-center text-[11px] uppercase tracking-wider text-slate-300/80">
            Melds on the table {layOffMode && <span className="text-gold">· click a meld to lay off</span>}
          </div>
          <div className="flex flex-wrap items-start justify-center gap-3">
            {snap.table_melds.length === 0 && (
              <div className="text-sm text-white/40">No melds yet.</div>
            )}
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
                      {owner} · {meld.kind} · {meld.points} pts
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

        {/* free-card prompt */}
        {freeForMe && (
          <div className="absolute inset-x-0 bottom-16 flex justify-center">
            <div className="flex items-center gap-3 rounded-xl border border-gold/40 bg-ink/90 px-4 py-2.5 shadow-2xl">
              <span className="text-sm">
                Claim the discarded <b>{snap.discard_top?.label}</b> for free?
              </span>
              <Button size="sm" onClick={() => send({ type: "claim_free_card" })}>
                Claim
              </Button>
              <Button size="sm" variant="outline" onClick={() => send({ type: "pass_free_card" })}>
                Pass
              </Button>
            </div>
          </div>
        )}

        {/* status hint */}
        <div className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2">
          <div
            className={cn(
              "rounded-full border border-white/10 bg-ink/85 px-4 py-1.5 text-sm shadow-xl",
              isMyTurn ? "text-gold" : "text-slate-200",
            )}
          >
            {statusText}
          </div>
        </div>
      </div>

      {/* ---------------- player dock ---------------- */}
      <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3 md:p-4">
        {mustLayTaken && (
          <div className="mb-3 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-sm text-amber-200">
            You took a card from the discard — you must use it in a meld before discarding.
          </div>
        )}

        {/* meld tray */}
        {(tray.length > 0 || (canAct && selected.length >= 3)) && (
          <div className="mb-3 flex flex-wrap items-center gap-3 rounded-xl border border-gold/25 bg-ink/40 p-3">
            <span className="rounded-full bg-gold/15 px-2 py-0.5 text-[11px] font-semibold text-gold">
              Meld tray
            </span>
            {tray.map((g, gi) => (
              <div key={gi} className="flex items-center gap-1 rounded-lg bg-black/20 p-1.5">
                {g.card_ids.map((id) => {
                  const card = snap.your_hand.find((h) => h.id === id);
                  return card ? <PlayingCard key={id} card={card} size="xs" /> : null;
                })}
                <span className="px-1 text-[10px] uppercase text-slate-400">{g.kind}</span>
              </div>
            ))}
            {tray.length === 0 && (
              <span className="text-sm text-slate-300">
                {selected.length} selected — add them as a meld.
              </span>
            )}
            <div className="ml-auto flex gap-2">
              {tray.length > 0 && (
                <Button size="sm" variant="ghost" onClick={clearTray}>
                  Clear
                </Button>
              )}
              <Button size="sm" onClick={layDown} disabled={tray.length === 0}>
                {goneOut ? "Lay down" : "Go out"} {tray.length > 0 ? `(${tray.length})` : ""}
              </Button>
            </div>
          </div>
        )}

        <div className="flex items-end justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-gold/20 font-bold text-gold">
              {mine.name.charAt(0).toUpperCase()}
            </span>
            <div className="leading-tight">
              <div className="text-sm font-semibold">
                {mine.name}{" "}
                {isMyTurn && (
                  <span className="rounded-full bg-gold/15 px-2 py-0.5 text-[11px] text-gold">
                    your turn
                  </span>
                )}
                {goneOut && (
                  <span className="ml-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] text-emerald-300">
                    out
                  </span>
                )}
              </div>
              <div className="text-[11px] text-slate-400">{snap.your_hand.length} cards</div>
            </div>
          </div>
          <div className="hidden text-[11px] text-slate-400 sm:block">
            click cards to select · build a meld · discard one to end your turn
          </div>
        </div>

        {/* hand — pt-6 gives headroom so a selected/hovered card's upward
            lift (translateY -16px) isn't clipped: overflow-x-auto forces
            overflow-y to clip too, so the scroll box needs top padding. */}
        <div className="mt-3 flex items-end overflow-x-auto pt-6 pb-2">
          {snap.your_hand.map((c, i) => (
            <div key={c.id} className={i ? "-ml-3" : ""}>
              <PlayingCard
                card={c}
                selected={selected.includes(c.id)}
                onClick={() => toggleSelect(c.id)}
              />
            </div>
          ))}
        </div>

        {/* actions — 2-col grid on phones (Discard spans full width), flex row on sm+ */}
        <div className="mt-3 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center">
          <Button disabled={!canDraw} onClick={() => send({ type: "draw_stock" })}>
            Draw from stock
          </Button>
          <Button
            variant="outline"
            disabled={!canDraw || !snap.discard_top}
            onClick={() => send({ type: "draw_discard" })}
          >
            Take discard {snap.discard_top ? `(${snap.discard_top.label})` : ""}
          </Button>
          <span className="mx-1 hidden h-6 w-px bg-white/10 sm:block" />
          <Button
            variant="outline"
            disabled={!canAct || selected.length < 3}
            onClick={() => addTrayGroup("run")}
          >
            Add as run
          </Button>
          <Button
            variant="outline"
            disabled={!canAct || selected.length < 3}
            onClick={() => addTrayGroup("set")}
          >
            Add as set
          </Button>
          <Button
            variant="destructive"
            className="col-span-2 sm:col-span-1 sm:ml-auto"
            disabled={!canAct || selected.length !== 1 || mustLayTaken}
            onClick={discard}
          >
            Discard {selected.length === 1 ? "selected" : ""}
          </Button>
        </div>
      </div>
    </div>
  );
}
