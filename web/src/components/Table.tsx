import { useStore } from "../store";
import { t } from "../i18n";
import { Button } from "./ui/button";
import { Lobby } from "./Lobby";
import { GameTable } from "./GameTable";
import { Scoreboard } from "./Scoreboard";
import { GameOverDialog, RoundOverDialog } from "./Dialogs";
import { HelpButton } from "./Help";
import { VersionBadge } from "./VersionBadge";

export function Table() {
  const { snapshot, connected, error, leave, dismissError, session } = useStore();

  return (
    <div className="min-h-screen min-h-dvh">
      {/* header */}
      <div className="sticky top-0 z-30 border-b border-white/10 bg-ink/80 backdrop-blur">
        <div className="mx-auto flex max-w-[1280px] items-center gap-2 px-3 py-2.5 sm:gap-3 sm:px-4">
          <div className="flex shrink-0 items-center gap-2 text-sm font-extrabold tracking-tight sm:text-base">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-gold text-ink">♣</span>
            {t.brand.rami}
            <span className="text-gold">{t.brand.suffix}</span>
          </div>
          <span className="shrink-0 rounded-full border border-white/15 px-2 py-0.5 font-mono text-xs tracking-widest text-gold">
            {session?.code}
          </span>
          <span
            className={
              "flex items-center gap-1.5 text-xs " +
              (connected ? "text-emerald-300" : "text-rose-300")
            }
          >
            <span
              className={
                "h-2 w-2 rounded-full " + (connected ? "bg-emerald-400" : "bg-rose-400")
              }
            />
            <span className="hidden sm:inline">
              {connected ? t.table.connected : t.table.connecting}
            </span>
          </span>
          <div className="ml-auto flex items-center gap-1">
            <VersionBadge className="hidden font-mono text-[11px] text-slate-500 sm:inline" />
            <HelpButton />
            <Button variant="ghost" size="sm" onClick={leave}>
              {t.table.leave}
            </Button>
          </div>
        </div>
      </div>

      {/* body */}
      <div className="mx-auto max-w-[1280px] px-3 py-4">
        {!snapshot ? (
          <div className="flex min-h-[60vh] items-center justify-center text-slate-400">
            {t.table.connectingTable}
          </div>
        ) : snapshot.phase === "lobby" ? (
          <Lobby snap={snapshot} />
        ) : (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
            <GameTable snap={snapshot} />
            <Scoreboard snap={snapshot} />
          </div>
        )}
      </div>

      {snapshot?.phase === "round_over" && <RoundOverDialog snap={snapshot} />}
      {snapshot?.phase === "game_over" && <GameOverDialog snap={snapshot} />}

      {/* error toast */}
      {error && (
        <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2">
          <button
            onClick={dismissError}
            className="rounded-lg border border-rose-400/40 bg-rose-500/20 px-4 py-2 text-sm text-rose-100 shadow-xl"
          >
            {error}
          </button>
        </div>
      )}
    </div>
  );
}
