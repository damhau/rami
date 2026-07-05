import type { Snapshot } from "../types";
import { useStore } from "../store";
import { Button } from "./ui/button";

export function Lobby({ snap }: { snap: Snapshot }) {
  const send = useStore((s) => s.send);
  const me = snap.you;
  const isHost = me === 0;
  const meReady = snap.players[me]?.ready ?? false;
  const canStart = snap.players.length >= 2;

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4">
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-400">Table code</div>
            <div className="font-mono text-2xl font-bold tracking-widest text-gold">{snap.code}</div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigator.clipboard?.writeText(snap.code)}
          >
            Copy code
          </Button>
        </div>

        <div className="mt-5 text-xs uppercase tracking-wide text-slate-400">
          Players ({snap.players.length}/4)
        </div>
        <ul className="mt-2 space-y-2">
          {snap.players.map((p) => (
            <li
              key={p.seat}
              className="flex items-center gap-3 rounded-lg bg-white/5 px-3 py-2 text-sm"
            >
              <span className="grid h-8 w-8 place-items-center rounded-full bg-gold/20 font-bold text-gold">
                {p.name.charAt(0).toUpperCase()}
              </span>
              <span className="font-medium">{p.name}</span>
              {p.seat === 0 && (
                <span className="rounded-full bg-gold/15 px-2 py-0.5 text-[11px] text-gold">
                  host
                </span>
              )}
              {p.seat === me && <span className="text-[11px] text-slate-400">(you)</span>}
              <span
                className={
                  "ml-auto rounded-full px-2 py-0.5 text-[11px] " +
                  (p.ready
                    ? "bg-emerald-500/15 text-emerald-300"
                    : "bg-white/10 text-slate-300")
                }
              >
                {p.ready ? "ready" : "not ready"}
              </span>
            </li>
          ))}
          {Array.from({ length: 4 - snap.players.length }).map((_, i) => (
            <li
              key={`empty-${i}`}
              className="flex items-center gap-3 rounded-lg border border-dashed border-white/10 px-3 py-2 text-sm text-slate-500"
            >
              <span className="grid h-8 w-8 place-items-center rounded-full border border-dashed border-white/15">
                +
              </span>
              Waiting for a player…
            </li>
          ))}
        </ul>

        <div className="mt-5 flex gap-2">
          <Button
            variant={meReady ? "outline" : "default"}
            className="flex-1"
            onClick={() => send({ type: "ready", ready: !meReady })}
          >
            {meReady ? "Not ready" : "I'm ready"}
          </Button>
          {isHost && (
            <Button
              className="flex-1"
              disabled={!canStart}
              onClick={() => send({ type: "start" })}
            >
              Start game
            </Button>
          )}
        </div>
        {isHost && !canStart && (
          <p className="mt-2 text-center text-xs text-slate-400">
            Need at least 2 players to start.
          </p>
        )}
        {!isHost && <p className="mt-2 text-center text-xs text-slate-400">Waiting for the host…</p>}
      </div>
    </div>
  );
}
