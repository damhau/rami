import type { CardView } from "../types";
import type { RunOption } from "../lib/melds";
import { t } from "../i18n";
import { Button } from "./ui/button";
import { PlayingCard, rankLabel } from "./PlayingCard";

function Overlay({ children }: { children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-ink p-6 shadow-2xl">
        {children}
      </div>
    </div>
  );
}

/** Render one run arrangement as a row of rank chips, jokers highlighted. */
function RunRow({ option, cards }: { option: RunOption; cards: CardView[] }) {
  const byId = new Map(cards.map((c) => [c.id, c]));
  return (
    <div className="flex flex-wrap items-center gap-1">
      {option.card_ids.map((id, i) => {
        const isJoker = byId.get(id)?.is_joker ?? false;
        return (
          <span
            key={id}
            className={
              "grid h-7 min-w-7 place-items-center rounded px-1.5 text-sm font-semibold " +
              (isJoker ? "bg-gold/20 text-gold ring-1 ring-gold/40" : "bg-white/10 text-white")
            }
            title={isJoker ? t.game.jokerEquals(rankLabel(option.ranks[i])) : undefined}
          >
            {rankLabel(option.ranks[i])}
            {isJoker && <span className="ml-0.5 text-[10px]">★</span>}
          </span>
        );
      })}
    </div>
  );
}

/** Ask how to lay an ambiguous selection: as a set, or as one of several run
 * arrangements (which fixes where each joker sits). Covers issues #2 and #9. */
export function MeldKindDialog({
  cards,
  setValid,
  runOptions,
  onPick,
  onCancel,
}: {
  cards: CardView[];
  setValid: boolean;
  runOptions: RunOption[];
  onPick: (kind: "set" | "run", cardIds: number[]) => void;
  onCancel: () => void;
}) {
  return (
    <Overlay>
      <h2 className="text-lg font-bold">{t.game.chooseMeld}</h2>
      <p className="mt-1 text-sm text-slate-400">{t.game.chooseMeldHint}</p>

      <div className="mt-4 space-y-2">
        {setValid && (
          <button
            onClick={() => onPick("set", cards.map((c) => c.id))}
            className="flex w-full items-center justify-between rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-left hover:border-gold/50 hover:bg-white/10"
          >
            <span className="font-semibold">{t.game.asSet}</span>
            <div className="flex -space-x-2">
              {cards.map((c) => (
                <PlayingCard key={c.id} card={c} size="xs" />
              ))}
            </div>
          </button>
        )}
        {runOptions.length > 0 && (
          <div className="rounded-xl border border-white/10 bg-white/5 p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              {t.game.asRunTitle}
            </div>
            <div className="space-y-2">
              {runOptions.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => onPick("run", opt.card_ids)}
                  className="flex w-full items-center justify-start rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-left hover:border-gold/50 hover:bg-white/10"
                >
                  <RunRow option={opt} cards={cards} />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="mt-5 flex justify-end">
        <Button variant="ghost" size="sm" onClick={onCancel}>
          {t.game.cancel}
        </Button>
      </div>
    </Overlay>
  );
}

/** Ask which end of a run a joker should extend (issue #11). */
export function JokerEndDialog({
  ranks,
  onPick,
  onCancel,
}: {
  ranks: number[];
  onPick: (asRank: number) => void;
  onCancel: () => void;
}) {
  return (
    <Overlay>
      <h2 className="text-lg font-bold">{t.game.chooseJokerEnd}</h2>
      <p className="mt-1 text-sm text-slate-400">{t.game.chooseJokerEndHint}</p>
      <div className="mt-4 flex gap-2">
        {ranks.map((r) => (
          <button
            key={r}
            onClick={() => onPick(r)}
            className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-4 text-center hover:border-gold/50 hover:bg-white/10"
          >
            <div className="text-xs text-slate-400">★</div>
            <div className="text-xl font-bold text-gold">{rankLabel(r)}</div>
          </button>
        ))}
      </div>
      <div className="mt-5 flex justify-end">
        <Button variant="ghost" size="sm" onClick={onCancel}>
          {t.game.cancel}
        </Button>
      </div>
    </Overlay>
  );
}
