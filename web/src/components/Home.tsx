import { useState } from "react";
import { createTable, createSolo, joinTable } from "../lib/api";
import { useStore } from "../store";
import { t } from "../i18n";
import { Button } from "./ui/button";
import { VersionBadge } from "./VersionBadge";

function codeFromUrl(): string {
  return (new URLSearchParams(location.search).get("t") ?? "").replace(/\D/g, "").slice(0, 4);
}

export function Home() {
  const enter = useStore((s) => s.enter);
  const [name, setName] = useState("");
  const [code, setCode] = useState(codeFromUrl);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bots, setBots] = useState(1);
  const invited = code.length === 4;

  const go = async (action: () => Promise<{ code: string; token: string; seat: number }>) => {
    setError(null);
    if (!name.trim()) {
      setError(t.home.needName);
      return;
    }
    setBusy(true);
    try {
      const joined = await action();
      enter({ code: joined.code, token: joined.token, you: joined.seat });
    } catch (e) {
      setError(e instanceof Error ? e.message : t.home.genericError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="app-shell-min mx-auto flex max-w-[1100px] items-start px-4 pt-6 sm:items-center sm:pt-0">
      <div className="grid w-full gap-4 sm:gap-8 md:grid-cols-2">
        <div>
          <div className="mb-3 flex items-center gap-2 text-xl font-extrabold tracking-tight sm:mb-6">
            <span className="grid h-8 w-8 place-items-center rounded-md bg-gold text-ink">♣</span>
            {t.brand.rami}
            <span className="text-gold">{t.brand.suffix}</span>
          </div>
          {/* Full marketing on tablet/desktop; on phones only a one-line tagline
              so the whole create/join screen fits without scrolling. */}
          <h1 className="hidden text-3xl font-extrabold leading-tight tracking-tight sm:block sm:text-4xl">
            {t.home.heroLead} <span className="text-gold">{t.home.heroName}</span>
            <br />
            {t.home.heroTail}
          </h1>
          <p className="mt-3 hidden max-w-md text-slate-300 sm:block">{t.home.blurb}</p>
          <p className="text-xs text-slate-400 sm:mt-3">{t.home.meta}</p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 shadow-2xl sm:p-6">
          <label className="text-xs font-medium uppercase tracking-wide text-slate-400">
            {t.home.yourName}
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t.home.namePlaceholder}
            maxLength={24}
            className="mt-1 w-full rounded-lg border border-white/10 bg-ink/60 px-3 py-2.5 text-sm outline-none focus:border-gold/60"
          />

          {invited ? (
            // Arrived via an invite link/QR: focus on joining that one table.
            <>
              <p className="mb-3 mt-4 text-sm text-gold">{t.home.invitedTo(code)}</p>
              <Button
                className="w-full"
                disabled={busy || code.length !== 4}
                onClick={() => go(() => joinTable(code.trim(), name.trim()))}
              >
                {t.home.joinTable(code)}
              </Button>
            </>
          ) : (
            <>
              <Button
                className="mt-4 w-full sm:mt-5"
                disabled={busy}
                onClick={() => go(() => createTable(name.trim()))}
              >
                {t.home.create}
              </Button>

              <div className="my-3 flex items-center gap-3 text-xs text-slate-500 sm:my-5">
                <span className="h-px flex-1 bg-white/10" />
                {t.home.orDivider}
                <span className="h-px flex-1 bg-white/10" />
              </div>

              <div className="rounded-xl border border-white/10 bg-ink/40 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{t.home.vsComputer}</span>
                  <div className="flex items-center gap-1">
                    <span className="mr-1 text-xs text-slate-400">{t.home.opponents}</span>
                    {[1, 2, 3].map((n) => (
                      <button
                        key={n}
                        onClick={() => setBots(n)}
                        className={
                          "h-7 w-7 rounded-md text-sm font-semibold " +
                          (bots === n ? "bg-gold text-ink" : "bg-white/10 text-slate-300")
                        }
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
                <Button
                  variant="outline"
                  className="mt-3 w-full"
                  disabled={busy}
                  onClick={() => go(() => createSolo(name.trim(), bots))}
                >
                  {t.home.vsComputer}
                </Button>
              </div>

              <div className="my-3 flex items-center gap-3 text-xs text-slate-500 sm:my-5">
                <span className="h-px flex-1 bg-white/10" />
                {t.home.orJoin}
                <span className="h-px flex-1 bg-white/10" />
              </div>

              <div className="flex items-stretch gap-2">
                <input
                  value={code}
                  inputMode="numeric"
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 4))}
                  placeholder="1234"
                  className="w-full rounded-lg border border-white/10 bg-ink/60 px-3 py-2.5 text-center text-lg font-mono tracking-[0.4em] outline-none focus:border-gold/60"
                />
                <Button
                  variant="outline"
                  disabled={busy || code.length !== 4}
                  onClick={() => go(() => joinTable(code.trim(), name.trim()))}
                >
                  {t.home.join}
                </Button>
              </div>
            </>
          )}

          {error && <p className="mt-4 text-sm text-rose-300">{error}</p>}
        </div>
      </div>
      <VersionBadge className="fixed bottom-3 right-4 font-mono text-[11px] text-slate-600" />
    </div>
  );
}
