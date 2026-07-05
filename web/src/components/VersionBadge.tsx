import { useEffect, useState } from "react";
import { getVersion } from "../lib/api";

// Fetched once per page load and shared across mounts.
let cached: string | null = null;

/** Shows the running app version (from the backend, sourced from pyproject.toml). */
export function VersionBadge({ className }: { className?: string }) {
  const [version, setVersion] = useState(cached ?? "");

  useEffect(() => {
    if (cached !== null) return;
    getVersion().then((v) => {
      cached = v;
      setVersion(v);
    });
  }, []);

  if (!version) return null;
  return <span className={className}>v{version}</span>;
}
