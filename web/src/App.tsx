import { useEffect } from "react";
import { loadSession, useStore } from "./store";
import { Home } from "./components/Home";
import { Table } from "./components/Table";

export function App() {
  const session = useStore((s) => s.session);
  const enter = useStore((s) => s.enter);

  // Rejoin a saved table on load (survives reloads / app restarts). If the table
  // is gone, the socket closes with 4404 and the store drops back to Home.
  useEffect(() => {
    if (!useStore.getState().session) {
      const saved = loadSession();
      if (saved) enter(saved);
    }
  }, [enter]);

  return session ? <Table /> : <Home />;
}
