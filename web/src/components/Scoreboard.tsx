import type { Snapshot } from "../types";
import { useStore } from "../store";

export function Scoreboard({ snap }: { snap: Snapshot }) {
  const log = useStore((s) => s.log);
  const dealer = snap.players.find((p) => p.seat === snap.dealer_seat);

  return (
    <aside className="flex flex-col gap-4">
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Scoreboard</h3>
          <span className="rounded-full bg-white/10 px-2 py-0.5 text-[11px] text-slate-300">
            round {snap.round_no}/11
          </span>
        </div>
        <table className="mt-3 w-full text-sm">
          <thead className="text-slate-400">
            <tr className="text-left">
              <th className="font-medium">Player</th>
              <th className="text-right font-medium">Hand</th>
              <th className="text-right font-medium">Total</th>
            </tr>
          </thead>
          <tbody>
            {snap.players.map((p) => (
              <tr key={p.seat} className="border-t border-white/5">
                <td className="py-1.5">
                  <span className={p.seat === snap.you ? "font-semibold text-gold" : ""}>
                    {p.name}
                  </span>
                  {p.has_gone_out && (
                    <span className="ml-1 text-[10px] text-emerald-300">▣ out</span>
                  )}
                </td>
                <td className="text-right text-slate-300">{p.hand_count}</td>
                <td className="text-right font-semibold">{p.total_score}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs text-slate-400">Lowest total after round 11 wins.</p>
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm">
        <h3 className="mb-2 font-semibold">This round</h3>
        <ul className="space-y-1.5 text-slate-300">
          <li className="flex justify-between">
            <span>Contract</span>
            <span className="text-right">{snap.contract?.label ?? "—"}</span>
          </li>
          <li className="flex justify-between">
            <span>Min. to go out</span>
            <span>{snap.go_out_min_points} pts</span>
          </li>
          <li className="flex justify-between">
            <span>Dealer</span>
            <span>{dealer?.name ?? "—"}</span>
          </li>
          <li className="flex justify-between">
            <span>Stock</span>
            <span>{snap.stock_count} cards</span>
          </li>
        </ul>
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3 text-xs text-slate-400">
        <div className="mb-1 font-semibold text-slate-200">Log</div>
        <div className="max-h-40 space-y-1 overflow-y-auto">
          {log.length === 0 && <div className="text-slate-500">No moves yet.</div>}
          {log.map((l) => (
            <div key={l.id}>{l.text}</div>
          ))}
        </div>
      </div>
    </aside>
  );
}
