import { useStore } from "./store";
import { Home } from "./components/Home";
import { Table } from "./components/Table";

export function App() {
  const session = useStore((s) => s.session);
  return session ? <Table /> : <Home />;
}
