import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import type { Snapshot } from "../types";
import { useStore } from "../store";
import { t } from "../i18n";
import { Button } from "./ui/button";

export function Lobby({ snap }: { snap: Snapshot }) {
  const send = useStore((s) => s.send);
  const me = snap.you;
  const isHost = me === 0;
  const canStart = snap.players.length >= 2;
  const [copied, setCopied] = useState(false);

  const inviteUrl = `${location.origin}${location.pathname}?t=${snap.code}`;
  const copyLink = async () => {
    await navigator.clipboard?.writeText(inviteUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4">
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-400">{t.lobby.tableCode}</div>
            <div className="font-mono text-3xl font-bold tracking-[0.3em] text-gold">{snap.code}</div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Button variant="outline" size="sm" onClick={() => navigator.clipboard?.writeText(snap.code)}>
              {t.lobby.copyCode}
            </Button>
            <Button variant="outline" size="sm" onClick={copyLink}>
              {copied ? t.lobby.linkCopied : t.lobby.copyLink}
            </Button>
          </div>
        </div>

        <div className="mt-5 flex flex-col items-center gap-2 rounded-xl bg-white/5 p-4">
          <div className="rounded-lg bg-white p-2.5">
            <QRCodeSVG value={inviteUrl} size={132} />
          </div>
          <span className="text-xs text-slate-400">{t.lobby.scanToJoin}</span>
        </div>

        <div className="mt-5 text-xs uppercase tracking-wide text-slate-400">
          {t.lobby.players(snap.players.length)}
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
                  {t.lobby.host}
                </span>
              )}
              {p.seat === me && <span className="text-[11px] text-slate-400">{t.lobby.you}</span>}
              <span
                className={
                  "ml-auto h-2.5 w-2.5 rounded-full " +
                  (p.connected ? "bg-emerald-400" : "bg-slate-500")
                }
                title={p.connected ? t.table.connected : t.table.connecting}
              />
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
              {t.lobby.waitingPlayer}
            </li>
          ))}
        </ul>

        {isHost && (
          <Button
            className="mt-5 w-full"
            disabled={!canStart}
            onClick={() => send({ type: "start" })}
          >
            {t.lobby.start}
          </Button>
        )}
        {isHost && !canStart && (
          <p className="mt-2 text-center text-xs text-slate-400">{t.lobby.needTwo}</p>
        )}
        {!isHost && <p className="mt-5 text-center text-xs text-slate-400">{t.lobby.waitingHost}</p>}
      </div>
    </div>
  );
}
