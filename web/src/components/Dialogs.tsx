import type { Snapshot } from "../types";
import { useStore } from "../store";
import { t } from "../i18n";
import { Button } from "./ui/button";

function Overlay({ children }: { children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-ink p-6 shadow-2xl">
        {children}
      </div>
    </div>
  );
}

export function RoundOverDialog({ snap }: { snap: Snapshot }) {
  const send = useStore((s) => s.send);
  const isHost = snap.you === 0;
  const winner = snap.players.find((p) => (snap.last_round_scores[p.seat] ?? 1) === 0);

  return (
    <Overlay>
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-full bg-emerald-500/20 text-xl text-emerald-300">
          ▣
        </span>
        <div>
          <h2 className="text-xl font-bold">{t.dialogs.roundFinished(snap.round_no)}</h2>
          <p className="text-sm text-slate-300">
            {(() => {
              const [name, tail] = t.dialogs.wentOutScores0(winner?.name ?? "");
              return (
                <>
                  <b className="text-gold">{name}</b>
                  {tail}
                </>
              );
            })()}
          </p>
        </div>
      </div>

      <table className="mt-5 w-full text-sm">
        <thead className="text-slate-400">
          <tr className="text-left">
            <th className="font-medium">{t.dialogs.player}</th>
            <th className="text-right font-medium">{t.dialogs.round}</th>
            <th className="text-right font-medium">{t.dialogs.total}</th>
          </tr>
        </thead>
        <tbody>
          {snap.players.map((p) => (
            <tr key={p.seat} className="border-t border-white/5">
              <td className="py-2 font-medium">{p.name}</td>
              <td className="text-right">{snap.last_round_scores[p.seat] ?? 0}</td>
              <td className="text-right font-semibold">{p.total_score}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-6 flex justify-end">
        {isHost ? (
          <Button onClick={() => send({ type: "next_round" })}>{t.dialogs.nextRound}</Button>
        ) : (
          <p className="text-sm text-slate-400">{t.dialogs.waitingHostNext}</p>
        )}
      </div>
    </Overlay>
  );
}

export function GameOverDialog({ snap }: { snap: Snapshot }) {
  const leave = useStore((s) => s.leave);
  const standings = snap.standings ?? [];
  const medals = ["①", "②", "③", "④"];

  return (
    <Overlay>
      <div className="text-center">
        <div className="text-5xl">🏆</div>
        <h2 className="mt-2 text-2xl font-extrabold">{t.dialogs.wins(standings[0]?.name ?? "")}</h2>
        <p className="text-slate-300">{t.dialogs.lowestWins}</p>
      </div>

      <div className="mx-auto mt-6 max-w-sm space-y-2">
        {standings.map((s, i) => (
          <div
            key={s.seat}
            className={
              "flex items-center justify-between rounded-xl px-4 py-3 " +
              (i === 0 ? "border border-gold/30 bg-gold/10" : "bg-white/5")
            }
          >
            <span className="flex items-center gap-2 font-semibold">
              <span className={i === 0 ? "text-gold" : "text-slate-400"}>{medals[i] ?? i + 1}</span>
              {s.name}
            </span>
            <span className="font-bold">{s.total}</span>
          </div>
        ))}
      </div>

      <div className="mt-7 flex justify-center">
        <Button variant="outline" onClick={leave}>
          {t.dialogs.backHome}
        </Button>
      </div>
    </Overlay>
  );
}
