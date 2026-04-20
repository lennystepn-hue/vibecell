# Phase 3 — Consent Screen + Connections Settings Page

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Replace the Phase-1 JSON consent stub with a branded Vue consent screen. Ship the `/settings/connections` page for listing and revoking OAuth clients + CLI devices. Add the `/api/v1/connections` unified endpoint (merges OAuth clients with CLI devices). Add Playwright E2E for allow + deny paths.

**Architecture:** Two new Vue pages (`OAuthConsent.vue`, `Connections.vue`). One new backend router (`connections.py`) merging `oauth_clients` + `cli_devices` into a single list. `/oauth/authorize` (Phase 1 returned JSON) now serves the Vue app for browser requests and keeps JSON for explicit `Accept: application/json`. Uses the existing Pinia store pattern.

**Tech Stack:** Vue 3 composition API + `<script setup>`, Pinia, Vue Router, Tailwind + Cockpit tokens, Playwright for E2E.

**Prerequisite:** Phases 1 + 2 complete.

---

## File structure produced by this phase

```
backend/
├── app/
│   ├── api/v1/connections.py          # GET /api/v1/connections, DELETE /api/v1/connections/{id}
│   └── services/connections.py        # merge + revoke service
└── tests/
    ├── test_connections_list.py
    └── test_connections_revoke.py

frontend/
├── src/
│   ├── pages/
│   │   ├── OAuthConsent.vue
│   │   └── Connections.vue
│   ├── stores/
│   │   └── connections.ts
│   ├── api/
│   │   └── connections.ts             # typed client
│   └── router.ts                       # (modify) add routes
├── tests/e2e/
│   ├── oauth-consent-allow.spec.ts
│   └── oauth-consent-deny.spec.ts
```

---

## Task 3.1 — Connections service (merge OAuth + CLI devices)

**Files:**
- Create: `backend/app/services/connections.py`
- Create: `backend/tests/test_connections_service.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_connections_service.py
from app.services.connections import ConnectionsService


async def test_list_merges_oauth_and_cli(async_session, user_workspace, registered_oauth_client, cli_device_fixture) -> None:
    svc = ConnectionsService(async_session)
    rows = await svc.list_for_user(user_id=user_workspace.owner_id)
    kinds = {r["type"] for r in rows}
    assert "oauth" in kinds
    assert "cli" in kinds


async def test_list_sorted_by_last_used_desc(async_session, user_workspace, two_oauth_clients_with_different_usage) -> None:
    svc = ConnectionsService(async_session)
    rows = await svc.list_for_user(user_id=user_workspace.owner_id)
    dates = [r["last_used_at"] for r in rows if r["last_used_at"]]
    assert dates == sorted(dates, reverse=True)


async def test_revoke_oauth_client(async_session, registered_oauth_client) -> None:
    svc = ConnectionsService(async_session)
    await svc.revoke("oauth", registered_oauth_client.id)
    row = await async_session.get(type(registered_oauth_client), registered_oauth_client.id)
    assert row.revoked_at is not None


async def test_revoke_cli_device(async_session, cli_device_fixture) -> None:
    svc = ConnectionsService(async_session)
    await svc.revoke("cli", cli_device_fixture.id)
    # Row should be deleted
    row = await async_session.get(type(cli_device_fixture), cli_device_fixture.id)
    assert row is None
```

- [ ] **Step 2: Implement service**

```python
# backend/app/services/connections.py
"""Unified Connections view — merges oauth_clients with cli_devices.

Used by /settings/connections page.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.audit import McpAuditLog
from app.oauth.models import OAuthAccessToken, OAuthClient, OAuthRefreshToken
from app.oauth.tokens import JTIBlacklist
from app.services.cli_devices import CLIDevice  # existing from Spec 3


class ConnectionsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        oauth_rows = (await self.db.execute(
            select(OAuthClient).where(
                OAuthClient.registered_by_user_id == user_id,
                OAuthClient.revoked_at.is_(None),
            )
        )).scalars().all()

        cli_rows = (await self.db.execute(
            select(CLIDevice).where(CLIDevice.user_id == user_id)
        )).scalars().all()

        results: list[dict[str, Any]] = []
        for c in oauth_rows:
            stats = await self._client_stats(c.client_id)
            results.append({
                "id": c.id,
                "type": "oauth",
                "name": c.client_name or "Unnamed MCP Client",
                "icon": self._icon_for(c.client_name),
                "connected_at": c.created_at,
                "last_used_at": c.last_used_at,
                "tool_calls_today": stats["today"],
                "tool_calls_total": stats["total"],
                "workspace_id": None,  # oauth clients aren't workspace-bound at registration
            })
        for d in cli_rows:
            results.append({
                "id": d.id,
                "type": "cli",
                "name": f"Device: {d.label}",
                "icon": "cli",
                "connected_at": d.paired_at,
                "last_used_at": d.last_sync_at,
                "tool_calls_today": 0,
                "tool_calls_total": 0,
                "workspace_id": d.workspace_id,
            })

        def sort_key(r: dict) -> datetime:
            return r["last_used_at"] or datetime.min.replace(tzinfo=timezone.utc)

        results.sort(key=sort_key, reverse=True)
        return results

    async def _client_stats(self, client_id: str) -> dict[str, int]:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today = (await self.db.execute(
            select(func.count(McpAuditLog.id)).where(
                McpAuditLog.client_id == client_id,
                McpAuditLog.called_at >= today_start,
            )
        )).scalar_one()
        total = (await self.db.execute(
            select(func.count(McpAuditLog.id)).where(McpAuditLog.client_id == client_id)
        )).scalar_one()
        return {"today": int(today), "total": int(total)}

    @staticmethod
    def _icon_for(name: str | None) -> str:
        if not name:
            return "generic"
        lower = name.lower()
        if "claude" in lower: return "claude"
        if "cursor" in lower: return "cursor"
        if "zed" in lower: return "zed"
        if "windsurf" in lower: return "windsurf"
        return "generic"

    async def revoke(self, kind: str, connection_id: str) -> None:
        now = datetime.now(timezone.utc)
        if kind == "oauth":
            row = await self.db.get(OAuthClient, connection_id)
            if row is None:
                return
            row.revoked_at = now
            # Blacklist all live access tokens for this client
            access_rows = (await self.db.execute(
                select(OAuthAccessToken).where(
                    OAuthAccessToken.client_id == row.client_id,
                    OAuthAccessToken.revoked_at.is_(None),
                    OAuthAccessToken.expires_at > now,
                )
            )).scalars().all()
            for ar in access_rows:
                ar.revoked_at = now
                ttl = max(1, int(ar.expires_at.timestamp()) - int(now.timestamp()))
                await JTIBlacklist().add(ar.jti, ttl_seconds=ttl)
            # Invalidate all refresh tokens
            await self.db.execute(
                select(OAuthRefreshToken).where(
                    OAuthRefreshToken.client_id == row.client_id,
                    OAuthRefreshToken.revoked_at.is_(None),
                )
            )  # iterate and flag
            refresh_rows = (await self.db.execute(
                select(OAuthRefreshToken).where(
                    OAuthRefreshToken.client_id == row.client_id,
                    OAuthRefreshToken.revoked_at.is_(None),
                )
            )).scalars().all()
            for rr in refresh_rows:
                rr.revoked_at = now
            return
        if kind == "cli":
            row = await self.db.get(CLIDevice, connection_id)
            if row is not None:
                await self.db.delete(row)
            return
        raise ValueError(f"Unknown connection kind: {kind}")
```

- [ ] **Step 3: Run tests + commit**

```bash
cd backend && uv run pytest tests/test_connections_service.py -v  # PASS
git add backend/app/services/connections.py backend/tests/test_connections_service.py
git commit -m "feat(connections): unified service — list + revoke across oauth_clients + cli_devices"
```

---

## Task 3.2 — `/api/v1/connections` endpoint

**Files:**
- Create: `backend/app/api/v1/connections.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_connections_api.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_connections_api.py
async def test_list_connections_requires_auth(client) -> None:
    resp = await client.get("/api/v1/connections")
    assert resp.status_code == 401


async def test_list_returns_merged_view(authed_client, user_workspace, registered_oauth_client, cli_device_fixture) -> None:
    resp = await authed_client.get("/api/v1/connections")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    kinds = {r["type"] for r in body}
    assert kinds >= {"oauth", "cli"}
    for r in body:
        for f in ("id", "type", "name", "icon", "connected_at"):
            assert f in r


async def test_revoke_oauth_connection(authed_client, registered_oauth_client) -> None:
    resp = await authed_client.delete(f"/api/v1/connections/{registered_oauth_client.id}?kind=oauth")
    assert resp.status_code == 204
    # It no longer appears in the list
    listing = (await authed_client.get("/api/v1/connections")).json()
    assert not any(r["id"] == registered_oauth_client.id for r in listing)


async def test_revoke_cli_connection(authed_client, cli_device_fixture) -> None:
    resp = await authed_client.delete(f"/api/v1/connections/{cli_device_fixture.id}?kind=cli")
    assert resp.status_code == 204


async def test_revoke_unknown_kind_returns_400(authed_client) -> None:
    resp = await authed_client.delete("/api/v1/connections/abc?kind=other")
    assert resp.status_code == 400
```

- [ ] **Step 2: Implement router**

```python
# backend/app/api/v1/connections.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import require_user
from app.core.db import get_db
from app.services.connections import ConnectionsService

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])


@router.get("")
async def list_connections(
    user = Depends(require_user), db: AsyncSession = Depends(get_db),
) -> list[dict]:
    svc = ConnectionsService(db)
    return await svc.list_for_user(user_id=user.id)


@router.delete("/{connection_id}", status_code=204)
async def revoke_connection(
    connection_id: str, kind: str = Query(...),
    user = Depends(require_user), db: AsyncSession = Depends(get_db),
) -> Response:
    if kind not in ("oauth", "cli"):
        raise HTTPException(400, "invalid_kind")
    svc = ConnectionsService(db)
    await svc.revoke(kind, connection_id)
    return Response(status_code=204)
```

- [ ] **Step 3: Mount + run tests**

Add to `main.py`:
```python
from app.api.v1.connections import router as connections_router
app.include_router(connections_router)
```

Run: `cd backend && uv run pytest tests/test_connections_api.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/connections.py backend/app/main.py backend/tests/test_connections_api.py
git commit -m "feat(api): GET /api/v1/connections + DELETE revoke (polymorphic oauth/cli)"
```

---

## Task 3.3 — Frontend API client + Pinia store for connections

**Files:**
- Create: `frontend/src/api/connections.ts`
- Create: `frontend/src/stores/connections.ts`

- [ ] **Step 1: Write API client**

```typescript
// frontend/src/api/connections.ts
import { apiFetch } from "@/api/client";

export type ConnectionType = "oauth" | "cli";

export interface Connection {
  id: string;
  type: ConnectionType;
  name: string;
  icon: "claude" | "cursor" | "zed" | "windsurf" | "cli" | "generic";
  connected_at: string;
  last_used_at: string | null;
  tool_calls_today: number;
  tool_calls_total: number;
  workspace_id: string | null;
}

export async function listConnections(): Promise<Connection[]> {
  return apiFetch<Connection[]>("/api/v1/connections");
}

export async function revokeConnection(id: string, kind: ConnectionType): Promise<void> {
  await apiFetch(`/api/v1/connections/${id}?kind=${kind}`, { method: "DELETE" });
}
```

- [ ] **Step 2: Write Pinia store**

```typescript
// frontend/src/stores/connections.ts
import { defineStore } from "pinia";
import { ref } from "vue";

import { listConnections, revokeConnection, type Connection, type ConnectionType } from "@/api/connections";

export const useConnectionsStore = defineStore("connections", () => {
  const list = ref<Connection[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function refresh() {
    loading.value = true;
    error.value = null;
    try {
      list.value = await listConnections();
    } catch (e: any) {
      error.value = e?.message ?? "Failed to load connections";
    } finally {
      loading.value = false;
    }
  }

  async function revoke(id: string, kind: ConnectionType) {
    await revokeConnection(id, kind);
    list.value = list.value.filter((c) => c.id !== id);
  }

  return { list, loading, error, refresh, revoke };
});
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/connections.ts frontend/src/stores/connections.ts
git commit -m "feat(frontend): connections API client + Pinia store"
```

---

## Task 3.4 — `/settings/connections` page

**Files:**
- Create: `frontend/src/pages/Connections.vue`
- Modify: `frontend/src/router.ts` (register route)

- [ ] **Step 1: Write the page**

```vue
<!-- frontend/src/pages/Connections.vue -->
<script setup lang="ts">
import { onMounted, ref } from "vue";

import Card from "@/components/ui/Card.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useConnectionsStore, type Connection } from "@/stores/connections";

const connections = useConnectionsStore();
const revokeTarget = ref<Connection | null>(null);

onMounted(() => connections.refresh());

function relative(ts: string | null): string {
  if (!ts) return "never";
  const ms = Date.now() - new Date(ts).getTime();
  if (ms < 60_000) return "just now";
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
  return `${Math.floor(ms / 86_400_000)}d ago`;
}

async function confirmRevoke() {
  if (!revokeTarget.value) return;
  await connections.revoke(revokeTarget.value.id, revokeTarget.value.type);
  revokeTarget.value = null;
}
</script>

<template>
  <div class="max-w-[900px] mx-auto px-8 py-8">
    <header class="mb-6">
      <h1 class="text-display text-fg-primary tracking-tight">Connections</h1>
      <p class="text-body text-fg-muted mt-1">Apps and clients with access to your workspaces.</p>
    </header>

    <div v-if="connections.loading && connections.list.length === 0" class="text-fg-muted mono-label">
      loading…
    </div>

    <div v-else-if="connections.list.length === 0" class="glass rounded-lg p-6 text-center text-fg-muted">
      No connections yet. Click "Connect another app" below to add your first one.
    </div>

    <div v-else class="space-y-3">
      <Card v-for="c in connections.list" :key="c.id" class="p-4">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-start gap-3 min-w-0">
            <div class="w-10 h-10 rounded-md bg-bg-surface-hi flex items-center justify-center text-lg">
              <span v-if="c.icon === 'claude'">🔷</span>
              <span v-else-if="c.icon === 'cursor'">📐</span>
              <span v-else-if="c.icon === 'zed'">⚡</span>
              <span v-else-if="c.icon === 'windsurf'">🪂</span>
              <span v-else-if="c.icon === 'cli'">🪄</span>
              <span v-else>🔌</span>
            </div>
            <div class="min-w-0">
              <div class="text-body text-fg-primary font-medium truncate">{{ c.name }}</div>
              <div class="text-small text-fg-muted mt-0.5">
                {{ c.type === "oauth" ? "MCP client" : "Paired device" }} ·
                Connected {{ relative(c.connected_at) }} · Last used {{ relative(c.last_used_at) }}
              </div>
              <div v-if="c.type === 'oauth'" class="text-small text-fg-muted mt-1 tabular-nums">
                {{ c.tool_calls_today }} tool calls today · {{ c.tool_calls_total }} total
              </div>
            </div>
          </div>
          <button
            class="text-small text-fg-muted hover:text-fg-error px-3 py-1.5 rounded border border-border hover:border-fg-error transition-colors"
            @click="revokeTarget = c"
          >
            {{ c.type === "cli" ? "Unpair" : "Revoke" }}
          </button>
        </div>
      </Card>
    </div>

    <div class="mt-8">
      <RouterLink
        to="/"
        class="text-small text-fg-muted hover:text-fg-body"
      >
        + Connect another app
      </RouterLink>
    </div>

    <!-- Revoke confirm modal -->
    <div
      v-if="revokeTarget"
      class="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50"
      @click.self="revokeTarget = null"
    >
      <div class="glass rounded-lg p-6 max-w-md w-full mx-4">
        <h3 class="text-body text-fg-primary font-medium">
          {{ revokeTarget.type === "cli" ? "Unpair" : "Revoke" }} {{ revokeTarget.name }}?
        </h3>
        <p class="text-small text-fg-muted mt-2">
          This will disconnect {{ revokeTarget.name }} immediately. You can reconnect anytime.
        </p>
        <div class="flex justify-end gap-2 mt-6">
          <button
            class="px-3 py-2 text-body text-fg-muted hover:text-fg-body"
            @click="revokeTarget = null"
          >
            Cancel
          </button>
          <PrimaryButton danger @click="confirmRevoke">
            {{ revokeTarget.type === "cli" ? "Unpair" : "Revoke" }}
          </PrimaryButton>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Register route**

Modify `frontend/src/router.ts` — add:

```typescript
{
  path: "/settings/connections",
  name: "connections",
  component: () => import("@/pages/Connections.vue"),
  meta: { requiresAuth: true },
},
```

- [ ] **Step 3: Add sidebar link**

Modify the Sidebar component (e.g. `frontend/src/components/app/Sidebar.vue`) — add under Settings group:

```vue
<RouterLink to="/settings/connections" class="sidebar-item">Connections</RouterLink>
```

- [ ] **Step 4: Manual smoke — dev server**

```bash
cd frontend && pnpm dev
# Visit http://localhost:5173/settings/connections — expect list (empty in dev, no OAuth clients yet)
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Connections.vue frontend/src/router.ts frontend/src/components/app/Sidebar.vue
git commit -m "feat(frontend): /settings/connections — unified OAuth + CLI device list with revoke"
```

---

## Task 3.5 — `/oauth/authorize` Vue consent page

**Files:**
- Create: `frontend/src/pages/OAuthConsent.vue`
- Modify: `frontend/src/router.ts`
- Modify: `backend/app/oauth/server.py` (content negotiation — serve HTML for browsers, JSON for `Accept: application/json`)

- [ ] **Step 1: Update `/oauth/authorize` to do content-negotiation**

In `backend/app/oauth/server.py`, wrap the return of the GET authorize handler:

```python
from fastapi.responses import FileResponse

INDEX_HTML = "frontend/dist/index.html"  # served by nginx in prod; FastAPI in dev


@router.get("/authorize")
async def authorize(..., request: Request, ...):
    # ... existing validation + consent-state stash ...

    if "application/json" in request.headers.get("accept", ""):
        # Programmatic caller (tests, curl) → return JSON context
        return {...}

    # Browser caller → serve SPA and let the router load /oauth/consent
    return FileResponse(INDEX_HTML)
```

- [ ] **Step 2: Add frontend consent route**

Modify `frontend/src/router.ts`:

```typescript
{
  path: "/oauth/authorize",
  name: "oauth-consent",
  component: () => import("@/pages/OAuthConsent.vue"),
  meta: { requiresAuth: true },  // existing auth guard redirects to /login with next=
},
```

- [ ] **Step 3: Implement page**

```vue
<!-- frontend/src/pages/OAuthConsent.vue -->
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { apiFetch } from "@/api/client";

interface ConsentContext {
  client_id: string;
  client_name: string | null;
  redirect_uri: string;
  scope: string;
  state: string;
  workspaces: { id: string; slug: string; name: string }[];
}

const route = useRoute();
const consent = ref<ConsentContext | null>(null);
const error = ref<string | null>(null);
const pickedWs = ref<string>("");
const submitting = ref(false);

onMounted(async () => {
  try {
    consent.value = await apiFetch<ConsentContext>(
      `/oauth/authorize${window.location.search}`,
      { headers: { Accept: "application/json" } },
    );
    pickedWs.value = consent.value.workspaces[0]?.id ?? "";
  } catch (e: any) {
    error.value = e?.message ?? "Failed to load consent context";
  }
});

const clientIcon = computed(() => {
  const n = (consent.value?.client_name ?? "").toLowerCase();
  if (n.includes("claude")) return "🔷";
  if (n.includes("cursor")) return "📐";
  if (n.includes("zed")) return "⚡";
  if (n.includes("windsurf")) return "🪂";
  return "🔌";
});

async function allow() {
  if (!consent.value || !pickedWs.value) return;
  submitting.value = true;
  try {
    // POST /oauth/grant returns a 302; follow manually so window.location changes
    const resp = await fetch("/oauth/grant", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: consent.value.state, workspace_id: pickedWs.value }),
      redirect: "manual",
    });
    if (resp.type === "opaqueredirect" || resp.status === 302 || resp.status === 0) {
      const loc = resp.headers.get("location");
      if (loc) { window.location.href = loc; return; }
    }
    error.value = "Grant failed";
  } finally {
    submitting.value = false;
  }
}

async function deny() {
  if (!consent.value) return;
  const resp = await fetch("/oauth/deny", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state: consent.value.state, workspace_id: "" }),
    redirect: "manual",
  });
  const loc = resp.headers.get("location");
  if (loc) window.location.href = loc;
}
</script>

<template>
  <div class="max-w-[560px] mx-auto px-6 py-12">
    <header class="mb-6">
      <h1 class="text-display text-fg-primary tracking-tight">Connect to Vibecell</h1>
      <p class="text-body text-fg-muted mt-1" v-if="consent">
        {{ consent.client_name || "An MCP client" }} wants to connect
      </p>
    </header>

    <div v-if="error" class="glass rounded-lg p-4 border border-fg-error/40 text-fg-error">
      {{ error }}
    </div>

    <div v-else-if="!consent" class="text-fg-muted mono-label">loading consent context…</div>

    <div v-else class="space-y-5">
      <div class="glass rounded-lg p-4 flex items-start gap-3">
        <div class="w-10 h-10 rounded-md bg-bg-surface-hi flex items-center justify-center text-xl">
          {{ clientIcon }}
        </div>
        <div class="min-w-0">
          <div class="text-body text-fg-primary font-medium">
            {{ consent.client_name || "Unnamed MCP Client" }}
          </div>
          <div class="text-small text-fg-muted mt-0.5">
            Client ID: <span class="font-mono">{{ consent.client_id.slice(0, 16) }}…</span>
          </div>
          <div class="text-small text-fg-muted">
            Redirects to: <span class="font-mono">{{ consent.redirect_uri }}</span>
          </div>
        </div>
      </div>

      <section>
        <h2 class="text-small mono-label text-fg-muted mb-2">It will be able to:</h2>
        <ul class="text-body text-fg-body space-y-1">
          <li>✓ Read your projects, sessions, decisions, ideas, notes</li>
          <li>✓ Log sessions, create decisions, capture ideas</li>
          <li>✓ Append to project notes, record ships</li>
          <li>✓ Update project context (focus, next step, open questions)</li>
          <li class="text-fg-muted">✗ Cannot run local commands (CLI-only)</li>
          <li class="text-fg-muted">✗ Cannot access other workspaces</li>
        </ul>
      </section>

      <section>
        <label class="text-small mono-label text-fg-muted block mb-2">Connect to workspace</label>
        <select
          v-model="pickedWs"
          class="w-full h-11 px-3 rounded-md bg-bg-surface border border-border text-fg-body"
        >
          <option v-for="w in consent.workspaces" :key="w.id" :value="w.id">
            {{ w.name }} ({{ w.slug }})
          </option>
        </select>
      </section>

      <div class="flex justify-end gap-2 pt-4">
        <button class="px-3 py-2 text-body text-fg-muted hover:text-fg-body" @click="deny">
          Deny
        </button>
        <PrimaryButton :disabled="submitting" @click="allow">
          {{ submitting ? "Connecting…" : "Allow & Connect" }}
        </PrimaryButton>
      </div>

      <p class="text-small text-fg-muted pt-4 border-t border-border">
        You can revoke this connection anytime at
        <RouterLink to="/settings/connections" class="text-fg-body underline">
          vibecell.dev/settings/connections
        </RouterLink>
      </p>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Manual smoke**

Use `test-client` — a 20-line node script that runs OAuth against dev server:

```javascript
// scripts/test-oauth-consent.mjs (create + gitignore as a dev-only scratch)
const BASE = "http://localhost:8000";
const reg = await (await fetch(`${BASE}/oauth/register`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ client_name: "Claude Desktop", redirect_uris: ["http://127.0.0.1:12345/cb"] }),
})).json();

const verifier = "v" + "a".repeat(42);
const challenge = Buffer.from(
  await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))
).toString("base64url");

const url = `${BASE}/oauth/authorize?response_type=code&client_id=${reg.client_id}&redirect_uri=http%3A%2F%2F127.0.0.1%3A12345%2Fcb&code_challenge=${challenge}&code_challenge_method=S256&state=manual_test&scope=vibecell:tools`;
console.log("Open in browser:", url);
```

Run the script, follow the URL, verify the consent page renders correctly and clicking Allow redirects to `http://127.0.0.1:12345/cb?code=...`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/OAuthConsent.vue frontend/src/router.ts backend/app/oauth/server.py
git commit -m "feat(frontend): /oauth/authorize consent screen (Vue) + backend content negotiation"
```

---

## Task 3.6 — Playwright E2E (allow + deny)

**Files:**
- Create: `frontend/tests/e2e/oauth-consent-allow.spec.ts`
- Create: `frontend/tests/e2e/oauth-consent-deny.spec.ts`

- [ ] **Step 1: Write allow test**

```typescript
// frontend/tests/e2e/oauth-consent-allow.spec.ts
import { expect, test } from "@playwright/test";

test("allow path redirects to client redirect_uri with code", async ({ page, request }) => {
  // 1. Register a client via API
  const reg = await (await request.post("/oauth/register", {
    data: { client_name: "Claude Desktop", redirect_uris: ["http://127.0.0.1:12345/cb"] },
  })).json();

  // 2. Sign in via dev-mode magic-link (test fixture)
  await page.goto("/login");
  await page.getByLabel("Email").fill(process.env.TEST_USER_EMAIL!);
  await page.getByRole("button", { name: /send magic link/i }).click();
  // Dev mode: poll /api/v1/test/magic-link-token → auto-click
  const token = await page.evaluate(async (email) => {
    const r = await fetch(`/api/v1/test/magic-link-token?email=${email}`);
    return (await r.json()).token;
  }, process.env.TEST_USER_EMAIL!);
  await page.goto(`/auth/verify?token=${token}`);

  // 3. Hit /oauth/authorize
  const verifier = "v" + "a".repeat(42);
  const challenge = Buffer.from(
    await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))
  ).toString("base64url");
  const authUrl = `/oauth/authorize?response_type=code&client_id=${reg.client_id}&redirect_uri=${encodeURIComponent("http://127.0.0.1:12345/cb")}&code_challenge=${challenge}&code_challenge_method=S256&state=e2e&scope=vibecell:tools`;
  await page.goto(authUrl);

  // 4. Verify consent renders
  await expect(page.getByText("Claude Desktop")).toBeVisible();
  await expect(page.getByText("Connect to workspace")).toBeVisible();

  // 5. Click Allow & verify redirect
  const [navigation] = await Promise.all([
    page.waitForURL(/^http:\/\/127\.0\.0\.1:12345\/cb\?code=/),
    page.getByRole("button", { name: /allow & connect/i }).click(),
  ]);
  expect(page.url()).toContain("state=e2e");
});
```

- [ ] **Step 2: Write deny test**

```typescript
// frontend/tests/e2e/oauth-consent-deny.spec.ts
import { expect, test } from "@playwright/test";

test("deny path redirects with access_denied error", async ({ page, request }) => {
  const reg = await (await request.post("/oauth/register", {
    data: { client_name: "Claude Desktop", redirect_uris: ["http://127.0.0.1:12345/cb"] },
  })).json();

  // Sign in via dev magic-link helper
  await page.goto("/login");
  await page.getByLabel("Email").fill(process.env.TEST_USER_EMAIL!);
  await page.getByRole("button", { name: /send magic link/i }).click();
  const token = await page.evaluate(async (email) => {
    const r = await fetch(`/api/v1/test/magic-link-token?email=${email}`);
    return (await r.json()).token;
  }, process.env.TEST_USER_EMAIL!);
  await page.goto(`/auth/verify?token=${token}`);

  const verifier = "v" + "a".repeat(42);
  const challenge = Buffer.from(
    await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))
  ).toString("base64url");
  await page.goto(
    `/oauth/authorize?response_type=code&client_id=${reg.client_id}&redirect_uri=${encodeURIComponent("http://127.0.0.1:12345/cb")}&code_challenge=${challenge}&code_challenge_method=S256&state=e2e_deny&scope=vibecell:tools`,
  );

  await page.getByRole("button", { name: /^deny$/i }).click();
  await page.waitForURL(/error=access_denied/);
  expect(page.url()).toContain("state=e2e_deny");
});
```

- [ ] **Step 3: Run both**

```bash
cd frontend && pnpm test:e2e tests/e2e/oauth-consent-*.spec.ts
```
Expected: both PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/tests/e2e/oauth-consent-*.spec.ts
git commit -m "test(e2e): OAuth consent — allow path + deny path"
```

---

## End of Phase 3 — Checklist

- [ ] `/api/v1/connections` returns merged OAuth + CLI list
- [ ] `DELETE /api/v1/connections/{id}?kind=` revokes correctly
- [ ] `/oauth/authorize` renders the Vue consent page for browser callers
- [ ] `Accept: application/json` still gets the JSON context (tests + curl keep working)
- [ ] `/settings/connections` shows cards with revoke button
- [ ] Sidebar links to Connections
- [ ] Playwright E2E allow + deny paths pass
- [ ] Full `uv run pytest -q` + `pnpm test` green

Proceed to Phase 4.
