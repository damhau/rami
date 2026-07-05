import type { JoinedTable } from "../types";

async function request<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    const message = data?.error?.message ?? `Request failed (${res.status})`;
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export function createTable(name: string): Promise<JoinedTable> {
  return request<JoinedTable>("/api/v1/tables", { name });
}

export function joinTable(code: string, name: string): Promise<JoinedTable> {
  return request<JoinedTable>(`/api/v1/tables/${code.toUpperCase()}/join`, { name });
}

export function createSolo(name: string, bots: number): Promise<JoinedTable> {
  return request<JoinedTable>("/api/v1/tables/solo", { name, bots });
}

export async function getVersion(): Promise<string> {
  try {
    const res = await fetch("/api/v1/version");
    if (!res.ok) return "";
    const data = (await res.json()) as { version?: string };
    return data.version ?? "";
  } catch {
    return "";
  }
}
