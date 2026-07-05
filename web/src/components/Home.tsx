import { useState } from "react";
import { createTable, joinTable } from "../lib/api";
import { useStore } from "../store";
import { Button } from "./ui/button";

export function Home() {
  const enter = useStore((s) => s.enter);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const go = async (action: () => Promise<{ code: string; token: string; seat: number }>) => {
    setError(null);
    if (!name.trim()) {
      setError("Enter a display name first.");
      return;
    }
    setBusy(true);
    try {
      const t = await action();
      enter({ code: t.code, token: t.token, you: t.seat });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-[1100px] items-center px-4">
      <div className="grid w-full gap-8 md:grid-cols-2">
        <div>
          <div className="mb-6 flex items-center gap-2 text-xl font-extrabold tracking-tight">
            <span className="grid h-8 w-8 place-items-center rounded-md bg-gold text-ink">♣</span>
            Rami<span className="text-gold">Portugais</span>
          </div>
          <h1 className="text-4xl font-extrabold leading-tight tracking-tight">
            Play <span className="text-gold">Rami Portugais</span>
            <br />
            online with friends.
          </h1>
          <p className="mt-3 max-w-md text-slate-300">
            The 11-contract Portuguese Rummy. Create a table, share the code, and play in real time —
            no account needed.
          </p>
          <p className="mt-3 text-xs text-slate-400">2–4 players · 11 rounds · lowest score wins.</p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 shadow-2xl">
          <label className="text-xs font-medium uppercase tracking-wide text-slate-400">
            Your name
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Damien"
            maxLength={24}
            className="mt-1 w-full rounded-lg border border-white/10 bg-ink/60 px-3 py-2.5 text-sm outline-none focus:border-gold/60"
          />

          <Button
            className="mt-5 w-full"
            disabled={busy}
            onClick={() => go(() => createTable(name.trim()))}
          >
            + Create a table
          </Button>

          <div className="my-5 flex items-center gap-3 text-xs text-slate-500">
            <span className="h-px flex-1 bg-white/10" />
            or join
            <span className="h-px flex-1 bg-white/10" />
          </div>

          <div className="flex items-stretch gap-2">
            <input
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="RAMI-7F3K"
              className="w-full rounded-lg border border-white/10 bg-ink/60 px-3 py-2.5 text-sm uppercase tracking-widest outline-none focus:border-gold/60"
            />
            <Button
              variant="outline"
              disabled={busy || !code.trim()}
              onClick={() => go(() => joinTable(code.trim(), name.trim()))}
            >
              Join
            </Button>
          </div>

          {error && <p className="mt-4 text-sm text-rose-300">{error}</p>}
        </div>
      </div>
    </div>
  );
}
