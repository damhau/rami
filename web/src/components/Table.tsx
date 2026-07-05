import { useState } from "react";
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
  const [showScores, setShowScores] = useState(false);
  const inGame = !!snapshot && snapshot.phase !== "lobby";

  return (
    // Fixed to the viewport so the game is one screen; only inner regions scroll.
    <div className="flex h-screen h-dvh flex-col overflow-hidden">
      {/* header */}
      <header
        className="shrink-0 border-b border-white/10 bg-ink/80 backdrop-blur"
        style={{ paddingTop: "env(safe-area-inset-top)" }}
      >
        <div className="mx-auto flex max-w-[1280px] items-center gap-2 px-3 py-2.5 sm:gap-3 sm:px-4">
          <div className="flex shrink-0 items-center gap-2 text-sm font-extrabold tracking-tight sm:text-base">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-gold text-ink">♣</span>
            <span className="hidden sm:inline">{t.brand.rami}</span>
            <span className="hidden text-gold sm:inline">{t.brand.suffix}</span>
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
              className={"h-2 w-2 rounded-full " + (connected ? "bg-emerald-400" : "bg-rose-400")}
            />
            <span className="hidden sm:inline">
              {connected ? t.table.connected : t.table.connecting}
            </span>
          </span>
          <div className="ml-auto flex items-center gap-1">
            <VersionBadge className="hidden font-mono text-[11px] text-slate-500 sm:inline" />
            {inGame && (
              <Button
                variant="ghost"
                size="sm"
                className="lg:hidden"
                onClick={() => setShowScores(true)}
              >
                {t.scoreboard.title}
              </Button>
            )}
            <HelpButton />
            <Button variant="ghost" size="sm" onClick={leave}>
              {t.table.leave}
            </Button>
          </div>
        </div>
      </header>

      {/* body — fills the remaining height */}
      <div className="min-h-0 flex-1">
        <div className="mx-auto flex h-full w-full max-w-[1280px] flex-col px-3 py-3">
          {!snapshot ? (
            <div className="flex flex-1 items-center justify-center text-slate-400">
              {t.table.connectingTable}
            </div>
          ) : snapshot.phase === "lobby" ? (
            <div className="min-h-0 flex-1 overflow-y-auto">
              <Lobby snap={snapshot} />
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 gap-4">
              <div className="min-w-0 flex-1">
                <GameTable snap={snapshot} />
              </div>
              {/* Sidebar on large screens; a drawer on phones/tablets. */}
              <aside className="hidden w-[300px] shrink-0 overflow-y-auto lg:block">
                <Scoreboard snap={snapshot} />
              </aside>
            </div>
          )}
        </div>
      </div>

      {/* mobile scoreboard drawer */}
      {showScores && inGame && snapshot && (
        <div className="fixed inset-0 z-40 lg:hidden" onClick={() => setShowScores(false)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div
            className="absolute inset-x-0 bottom-0 max-h-[82dvh] overflow-y-auto rounded-t-2xl border-t border-white/10 bg-ink p-4 pb-8 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-semibold">{t.scoreboard.title}</h3>
              <button
                onClick={() => setShowScores(false)}
                aria-label="Fermer"
                className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 hover:bg-white/10 hover:text-white"
              >
                ✕
              </button>
            </div>
            <Scoreboard snap={snapshot} />
          </div>
        </div>
      )}

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
