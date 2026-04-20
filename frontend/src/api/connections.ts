export type ConnectionType = "oauth" | "cli";
export type ConnectionIcon = "claude" | "cursor" | "zed" | "windsurf" | "cli" | "generic";

export interface Connection {
  id: string;
  type: ConnectionType;
  name: string;
  icon: ConnectionIcon;
  connected_at: string | null;
  last_used_at: string | null;
  tool_calls_today: number;
  tool_calls_total: number;
  workspace_id: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || `HTTP ${res.status}`);
  }
  // 204 No Content
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

export async function listConnections(): Promise<Connection[]> {
  return request<Connection[]>("/api/v1/connections");
}

export async function revokeConnection(id: string, kind: ConnectionType): Promise<void> {
  await request<void>(`/api/v1/connections/${id}?kind=${kind}`, { method: "DELETE" });
}
