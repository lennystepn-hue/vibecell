# Phase 4 — Connect Button, Deep-Link, Docs, Metrics

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Close the UX loop — dashboard CTA + modal with one-click deep-link + copy-paste fallback. Publish docs page explaining the connect flow for each client (Claude Desktop, Cursor, Zed, Windsurf). Expose Prometheus metrics for `oauth_tokens_issued`, `mcp_tool_calls`, `mcp_auth_failures`, `mcp_active_connections`. Add a daily cron to clean orphan DCR clients + prune audit logs > 30 days.

**Architecture:** One new Vue component (`ConnectModal.vue`), dashboard CTA entry, docs markdown pages served under `/docs/`, Prometheus wiring via existing `prometheus_client` if wired or add it, one APScheduler cron in backend. No new DB tables.

**Tech Stack:** Vue 3, `prometheus_client` Python lib, APScheduler (already present for audit retention? verify).

**Prerequisite:** Phases 1–3 complete.

---

## File structure produced by this phase

```
backend/
├── app/
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── registry.py             # Prometheus counters/gauges definitions
│   │   └── endpoint.py             # GET /metrics handler
│   ├── jobs/
│   │   └── oauth_cleanup.py        # daily cron — orphan DCR clients + audit log prune
│   └── main.py                     # (modify) mount /metrics + register scheduler job

frontend/
├── src/
│   ├── components/
│   │   └── connections/
│   │       └── ConnectModal.vue
│   ├── pages/
│   │   └── Dashboard.vue           # (modify) add "Connect your editor" CTA
│   └── pages/
│       └── Connections.vue         # (modify) replace "+ Connect another app" with modal trigger

docs/
└── connect/
    ├── index.md                     # public docs page index
    ├── claude-desktop.md
    ├── claude-code.md
    ├── cursor.md
    ├── zed.md
    └── windsurf.md
```

---

## Task 4.1 — `ConnectModal.vue` component

**Files:**
- Create: `frontend/src/components/connections/ConnectModal.vue`

- [ ] **Step 1: Write the component**

```vue
<!-- frontend/src/components/connections/ConnectModal.vue -->
<script setup lang="ts">
import { ref } from "vue";

import PrimaryButton from "@/components/ui/PrimaryButton.vue";

defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: [] }>();

const tab = ref<"claude-desktop" | "claude-code" | "cursor" | "zed" | "windsurf">("claude-desktop");
const copied = ref(false);

const URL = "https://vibecell.dev";

function tryOneClick() {
  const deepLink = `claude://add-connector?url=${encodeURIComponent(URL)}`;
  window.location.href = deepLink;
}

async function copyUrl() {
  await navigator.clipboard.writeText(URL);
  copied.value = true;
  setTimeout(() => (copied.value = false), 1800);
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50"
    @click.self="emit('close')"
  >
    <div class="glass rounded-lg p-6 max-w-lg w-full mx-4">
      <div class="flex items-start justify-between mb-4">
        <h2 class="text-display text-fg-primary tracking-tight">Connect your editor</h2>
        <button class="text-fg-muted hover:text-fg-body" @click="emit('close')">✕</button>
      </div>

      <nav class="flex gap-1 mb-4 border-b border-border">
        <button
          v-for="t in ['claude-desktop', 'claude-code', 'cursor', 'zed', 'windsurf']"
          :key="t"
          class="px-3 py-2 text-small text-fg-muted hover:text-fg-body transition-colors"
          :class="{ 'text-fg-primary border-b-2 border-accent-primary -mb-px': tab === t }"
          @click="tab = t as any"
        >
          {{ t === "claude-desktop" ? "Claude Desktop" :
             t === "claude-code"    ? "Claude Code" :
             t === "cursor"         ? "Cursor" :
             t === "zed"            ? "Zed" : "Windsurf" }}
        </button>
      </nav>

      <div v-if="tab === 'claude-desktop'">
        <PrimaryButton @click="tryOneClick" class="w-full mb-4">
          Try one-click · opens Claude Desktop
        </PrimaryButton>
        <p class="text-small text-fg-muted text-center mb-4">— or copy the URL manually —</p>
        <ol class="text-body text-fg-body space-y-2 mb-4">
          <li>1. Open Claude Desktop → Settings → Connectors</li>
          <li>2. Click "Add Remote Server"</li>
          <li>3. Paste the URL below</li>
          <li>4. Follow the sign-in prompt in your browser</li>
        </ol>
      </div>

      <div v-else-if="tab === 'claude-code'">
        <p class="text-body text-fg-body mb-4">
          In your project's <code class="font-mono text-small">.mcp.json</code>:
        </p>
        <pre class="glass rounded p-3 text-small font-mono overflow-x-auto mb-4">{{ `{
  "mcpServers": {
    "vibecell": {
      "type": "http",
      "url": "${URL}/mcp"
    }
  }
}` }}</pre>
        <p class="text-small text-fg-muted">Claude Code discovers the OAuth flow automatically on first connection.</p>
      </div>

      <div v-else-if="tab === 'cursor'">
        <ol class="text-body text-fg-body space-y-2 mb-4">
          <li>1. Cursor → Settings → Model Context Protocol</li>
          <li>2. Add URL below, Cursor will prompt for OAuth</li>
        </ol>
      </div>

      <div v-else-if="tab === 'zed'">
        <ol class="text-body text-fg-body space-y-2 mb-4">
          <li>1. Zed → Settings → AI → Context Servers</li>
          <li>2. Click "Add Remote", paste URL below</li>
        </ol>
      </div>

      <div v-else>
        <ol class="text-body text-fg-body space-y-2 mb-4">
          <li>1. Windsurf → Settings → Cascade → MCP Servers</li>
          <li>2. Click "Add Remote Server", paste URL below</li>
        </ol>
      </div>

      <div class="flex items-center gap-2 glass rounded-md p-3">
        <code class="flex-1 text-small font-mono text-fg-body">{{ URL }}</code>
        <button
          class="text-small text-fg-muted hover:text-fg-body px-3 py-1 rounded border border-border"
          @click="copyUrl"
        >
          {{ copied ? "✓ Copied" : "Copy" }}
        </button>
      </div>

      <p class="text-small text-fg-muted mt-4 pt-4 border-t border-border">
        Works with any MCP client. Tools call local operations via
        <code class="font-mono">hangar.exe</code> (install with
        <code class="font-mono">curl vibecell.dev/install.sh | sh</code>).
      </p>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Wire into Connections.vue**

Modify `frontend/src/pages/Connections.vue` — replace the bottom "+ Connect another app" with a button that opens the modal:

```vue
<!-- Connections.vue changes -->
<script setup lang="ts">
import ConnectModal from "@/components/connections/ConnectModal.vue";
// ...
const connectOpen = ref(false);
</script>

<template>
  <!-- ... existing ... -->
    <div class="mt-8">
      <button
        class="text-small text-fg-muted hover:text-fg-body"
        @click="connectOpen = true"
      >
        + Connect another app
      </button>
    </div>

    <ConnectModal :open="connectOpen" @close="connectOpen = false" />
  <!-- ... -->
</template>
```

- [ ] **Step 3: Add dashboard CTA**

Modify `frontend/src/pages/Dashboard.vue` — if no OAuth connections yet, show a prominent CTA card:

```vue
<script setup lang="ts">
import ConnectModal from "@/components/connections/ConnectModal.vue";
import { useConnectionsStore } from "@/stores/connections";
import { onMounted, computed, ref } from "vue";

const connections = useConnectionsStore();
const connectOpen = ref(false);
const hasOAuthClient = computed(() => connections.list.some((c) => c.type === "oauth"));

onMounted(() => connections.refresh());
</script>

<template>
  <!-- existing dashboard content -->
  <section v-if="!connections.loading && !hasOAuthClient" class="glass rounded-lg p-6 mb-8 border border-accent-primary/20">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h2 class="text-body text-fg-primary font-medium">Connect your editor to Vibecell</h2>
        <p class="text-small text-fg-muted mt-1">
          Claude Desktop, Cursor, Zed, and other MCP clients can talk to Vibecell directly.
          Zero install — just sign in and allow.
        </p>
      </div>
      <button
        class="shrink-0 px-4 py-2 rounded-md bg-accent-primary text-fg-on-accent text-body font-medium hover:opacity-90 transition-opacity"
        @click="connectOpen = true"
      >
        Connect
      </button>
    </div>
  </section>
  <!-- ... -->
  <ConnectModal :open="connectOpen" @close="connectOpen = false" />
</template>
```

- [ ] **Step 4: Manual smoke**

```bash
cd frontend && pnpm dev
# Visit localhost:5173 → "Connect your editor" CTA should show
# Click → modal opens → tab through clients → copy URL works
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/connections/ConnectModal.vue frontend/src/pages/Connections.vue frontend/src/pages/Dashboard.vue
git commit -m "feat(frontend): ConnectModal with multi-client tabs + dashboard CTA"
```

---

## Task 4.2 — Public docs pages

**Files:**
- Create: `docs/connect/index.md`
- Create: `docs/connect/claude-desktop.md`
- Create: `docs/connect/claude-code.md`
- Create: `docs/connect/cursor.md`
- Create: `docs/connect/zed.md`
- Create: `docs/connect/windsurf.md`
- Modify: `backend/app/main.py` or nginx config to serve `/docs/*` as markdown-rendered HTML (reuse existing docs-site pattern if any; else just serve as static markdown linked from the modal "Learn more" link)

- [ ] **Step 1: Write `index.md`**

```markdown
<!-- docs/connect/index.md -->
# Connect your editor to Vibecell

Vibecell works with any MCP-compatible client. Pick yours:

- [Claude Desktop](./claude-desktop.md)
- [Claude Code](./claude-code.md)
- [Cursor](./cursor.md)
- [Zed](./zed.md)
- [Windsurf](./windsurf.md)

## What gets connected

Once authorized, your client can call 17 tools against your active Vibecell workspace:

**Read** — `ping`, `active`, `list`, `get`, `brief`, `search`, `recent_projects`, `claude_md`, `handover`
**Write** — `switch`, `log_session`, `update_context`, `decision`, `idea`, `note_append`, `ship`, `status`

## What stays local

`vibecell.run` — execute saved project commands with secret resolution — only works with the local
CLI (install via `curl vibecell.dev/install.sh | sh`). Remote clients cannot execute on your
machine by design.

## Revoking access

`vibecell.dev/settings/connections` shows every connected client with a revoke button.
Disconnection is immediate.
```

- [ ] **Step 2: Write `claude-desktop.md`**

```markdown
<!-- docs/connect/claude-desktop.md -->
# Connect Claude Desktop

**Requirements:** Claude Desktop 0.X+ with MCP connector support.

## One-click (recommended)

1. Open [vibecell.dev/settings/connections](https://vibecell.dev/settings/connections).
2. Click "Connect another app" → "Claude Desktop" tab → "Try one-click".
3. Claude Desktop opens; confirm "Add Vibecell as connector?".
4. A browser tab opens at vibecell.dev; pick your workspace → "Allow & Connect".
5. Claude Desktop now lists vibecell as a connected server. 17 tools available.

## Manual

If the one-click button does nothing:

1. Open Claude Desktop → Settings → Connectors → "Add Remote Server".
2. Enter URL: `https://vibecell.dev`.
3. Desktop discovers OAuth, opens a browser tab to sign in + consent.
4. Consent screen: pick workspace → "Allow & Connect".

## Troubleshooting

**"Server refused connection"** — Vibecell is not reachable from your network. Check `curl https://vibecell.dev/.well-known/oauth-authorization-server`.

**"Invalid redirect_uri"** — Claude Desktop has rotated its loopback port. Delete the connector in Desktop, retry.

**"Scope insufficient"** — Your token was issued before a scope change. Revoke at `vibecell.dev/settings/connections` and reconnect.
```

- [ ] **Step 3: Write `claude-code.md`**

```markdown
<!-- docs/connect/claude-code.md -->
# Connect Claude Code (CLI)

## Remote (zero-install beyond Claude Code itself)

Drop in your project root:

```json
// .mcp.json
{
  "mcpServers": {
    "vibecell": {
      "type": "http",
      "url": "https://vibecell.dev/mcp"
    }
  }
}
```

Restart Claude Code in that directory. First tool call triggers OAuth:
browser opens → pick workspace → allow. Token is cached under
`~/.claude/mcp-auth/vibecell.dev.json`.

## Local (for `vibecell.run` — command execution with secrets)

```bash
curl vibecell.dev/install.sh | sh
hangar pair
hangar daemon start
```

Then in `.mcp.json`:

```json
{
  "mcpServers": {
    "vibecell": {
      "type": "http",
      "url": "http://127.0.0.1:7421/mcp/v1",
      "headers": { "Authorization": "Bearer ${HANGAR_MCP_TOKEN}" }
    }
  }
}
```

The local daemon exposes all 18 tools including `vibecell.run`.
```

- [ ] **Step 4: Write `cursor.md`, `zed.md`, `windsurf.md`**

Each follows the same short pattern:

```markdown
# Connect Cursor

1. Cursor → Settings → Model Context Protocol.
2. Add remote server: `https://vibecell.dev`.
3. Cursor opens a browser for OAuth consent.
4. Pick workspace → Allow → tools available.
```

Similar for Zed (Settings → AI → Context Servers) and Windsurf (Settings → Cascade → MCP Servers).

- [ ] **Step 5: Commit**

```bash
git add docs/connect/
git commit -m "docs(connect): client-specific setup guides for Claude Desktop/Code, Cursor, Zed, Windsurf"
```

---

## Task 4.3 — Prometheus metrics

**Files:**
- Create: `backend/app/metrics/__init__.py` (empty)
- Create: `backend/app/metrics/registry.py`
- Create: `backend/app/metrics/endpoint.py`
- Modify: `backend/app/oauth/server.py` (emit)
- Modify: `backend/app/mcp/server.py` (emit)
- Modify: `backend/app/main.py` (mount `/metrics`)
- Modify: `backend/pyproject.toml` (add `prometheus_client`)
- Create: `backend/tests/test_metrics_endpoint.py`

- [ ] **Step 1: Add dep**

Run: `cd backend && uv add prometheus_client`

- [ ] **Step 2: Implement registry**

```python
# backend/app/metrics/registry.py
"""Prometheus metric registry for OAuth + MCP."""
from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge

REGISTRY = CollectorRegistry()

oauth_tokens_issued = Counter(
    "oauth_tokens_issued_total",
    "OAuth access tokens issued",
    labelnames=["client_name"],
    registry=REGISTRY,
)

oauth_authorize_outcomes = Counter(
    "oauth_authorize_redirects_total",
    "OAuth authorize redirects",
    labelnames=["outcome"],  # granted | denied | error
    registry=REGISTRY,
)

mcp_tool_calls = Counter(
    "mcp_tool_calls_total",
    "MCP tool calls",
    labelnames=["tool_name", "status"],  # status: ok | error | denied
    registry=REGISTRY,
)

mcp_auth_failures = Counter(
    "mcp_auth_failures_total",
    "MCP auth middleware rejections",
    labelnames=["reason"],  # missing_bearer | invalid_token | revoked_token | insufficient_scope
    registry=REGISTRY,
)

mcp_active_connections = Gauge(
    "mcp_active_connections",
    "Currently-valid OAuth access tokens (non-expired, non-revoked)",
    registry=REGISTRY,
)
```

- [ ] **Step 3: Implement endpoint**

```python
# backend/app/metrics/endpoint.py
from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.metrics.registry import REGISTRY

router = APIRouter()


@router.get("/metrics")
async def metrics_endpoint() -> Response:
    body = generate_latest(REGISTRY)
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)
```

- [ ] **Step 4: Emit in OAuth + MCP**

In `backend/app/oauth/server.py` — around token issuance:

```python
from app.metrics.registry import oauth_tokens_issued, oauth_authorize_outcomes

# after successful issuance in _token_from_code / _token_from_refresh:
oauth_tokens_issued.labels(client_name=client_row.client_name or "unknown").inc()

# in grant (success):
oauth_authorize_outcomes.labels(outcome="granted").inc()

# in deny:
oauth_authorize_outcomes.labels(outcome="denied").inc()
```

In `backend/app/mcp/server.py`, inside `_dispatch_tool_call` after status is set:

```python
from app.metrics.registry import mcp_tool_calls
mcp_tool_calls.labels(tool_name=name, status=status).inc()
```

In `backend/app/mcp/auth.py`, before each `raise HTTPException(...)`:

```python
from app.metrics.registry import mcp_auth_failures

# missing Bearer header
if not header.lower().startswith("bearer "):
    mcp_auth_failures.labels(reason="missing_bearer").inc()
    raise HTTPException(status_code=401, detail="missing_bearer", headers=_WWW_AUTH_HEADER)

# invalid/expired JWT
try:
    claims = verify_access_token(token)
except ValueError:
    mcp_auth_failures.labels(reason="invalid_token").inc()
    raise HTTPException(status_code=401, detail="invalid_token", headers=_WWW_AUTH_HEADER)

# revoked JTI
if await JTIBlacklist().is_revoked(claims.jti):
    mcp_auth_failures.labels(reason="revoked_token").inc()
    raise HTTPException(status_code=401, detail="revoked_token", headers=_WWW_AUTH_HEADER)

# insufficient scope
if "vibecell:tools" not in claims.scope.split():
    mcp_auth_failures.labels(reason="insufficient_scope").inc()
    raise HTTPException(status_code=403, detail="insufficient_scope", headers=_WWW_AUTH_HEADER)
```

- [ ] **Step 5: Mount**

```python
# backend/app/main.py
from app.metrics.endpoint import router as metrics_router
app.include_router(metrics_router)
```

- [ ] **Step 6: Test**

```python
# backend/tests/test_metrics_endpoint.py
async def test_metrics_endpoint_returns_prometheus_format(client) -> None:
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    text = resp.text
    assert "oauth_tokens_issued_total" in text
    assert "mcp_tool_calls_total" in text
    assert "mcp_active_connections" in text


async def test_tool_call_increments_counter(mcp_client, user_workspace_with_active_project, client) -> None:
    before = (await client.get("/metrics")).text
    await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.ping", "arguments": {}},
    })
    after = (await client.get("/metrics")).text
    # Expect the ping counter to have increased
    import re
    def count(body: str, tool: str) -> float:
        m = re.search(rf'mcp_tool_calls_total{{status="ok",tool_name="{tool}"}} (\d+\.?\d*)', body)
        return float(m.group(1)) if m else 0.0
    assert count(after, "vibecell.ping") > count(before, "vibecell.ping")
```

- [ ] **Step 7: Run + commit**

```bash
cd backend && uv run pytest tests/test_metrics_endpoint.py -v  # PASS
git add backend/app/metrics/ backend/app/main.py backend/app/oauth/server.py backend/app/mcp/server.py backend/app/mcp/auth.py backend/pyproject.toml backend/uv.lock backend/tests/test_metrics_endpoint.py
git commit -m "feat(metrics): Prometheus /metrics for OAuth + MCP (tokens_issued, tool_calls, auth_failures)"
```

---

## Task 4.4 — Cron: orphan DCR cleanup + audit log retention

**Files:**
- Create: `backend/app/jobs/__init__.py` (empty)
- Create: `backend/app/jobs/oauth_cleanup.py`
- Create: `backend/tests/test_oauth_cleanup_job.py`
- Modify: `backend/app/main.py` (schedule via APScheduler on startup)

- [ ] **Step 1: Test**

```python
# backend/tests/test_oauth_cleanup_job.py
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.jobs.oauth_cleanup import prune_audit_log, prune_orphan_clients
from app.mcp.audit import McpAuditLog
from app.oauth.models import OAuthClient


async def test_prune_orphan_clients_older_than_24h(async_session) -> None:
    old_orphan = OAuthClient(
        id="01OLD", client_id="dyn_old", client_name="old",
        redirect_uris=["http://127.0.0.1:1/cb"], scope="vibecell:tools",
        registered_by_user_id=None,
        created_at=datetime.now(timezone.utc) - timedelta(hours=48),
    )
    fresh_orphan = OAuthClient(
        id="01NEW", client_id="dyn_new", client_name="new",
        redirect_uris=["http://127.0.0.1:1/cb"], scope="vibecell:tools",
        registered_by_user_id=None,
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    async_session.add_all([old_orphan, fresh_orphan])
    await async_session.flush()

    removed = await prune_orphan_clients(async_session)
    assert removed == 1
    rows = (await async_session.execute(select(OAuthClient))).scalars().all()
    ids = {r.id for r in rows}
    assert "01NEW" in ids
    assert "01OLD" not in ids


async def test_prune_audit_log_older_than_30_days(async_session, registered_oauth_client, user_workspace) -> None:
    ancient = McpAuditLog(
        id="01ANC", client_id=registered_oauth_client.client_id,
        workspace_id=user_workspace.id, user_id=user_workspace.owner_id,
        tool_name="vibecell.ping",
        called_at=datetime.now(timezone.utc) - timedelta(days=45),
        duration_ms=1, status="ok",
    )
    recent = McpAuditLog(
        id="01REC", client_id=registered_oauth_client.client_id,
        workspace_id=user_workspace.id, user_id=user_workspace.owner_id,
        tool_name="vibecell.ping",
        called_at=datetime.now(timezone.utc) - timedelta(days=5),
        duration_ms=1, status="ok",
    )
    async_session.add_all([ancient, recent])
    await async_session.flush()

    removed = await prune_audit_log(async_session)
    assert removed == 1
    rows = (await async_session.execute(select(McpAuditLog))).scalars().all()
    ids = {r.id for r in rows}
    assert "01REC" in ids
    assert "01ANC" not in ids
```

- [ ] **Step 2: Implementation**

```python
# backend/app/jobs/oauth_cleanup.py
"""Daily maintenance — orphan DCR clients + audit log retention.

Scheduled by APScheduler in app/main.py on startup; safe to also run manually
via `uv run python -m app.jobs.oauth_cleanup`.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import async_session_maker
from app.mcp.audit import McpAuditLog
from app.oauth.models import OAuthClient

logger = logging.getLogger(__name__)


async def prune_orphan_clients(db: AsyncSession) -> int:
    """Delete OAuth clients registered via DCR that never authorized.

    Criteria: registered_by_user_id IS NULL AND created_at older than 24h.
    Returns count deleted.
    """
    s = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=s.OAUTH_DCR_ORPHAN_TTL_HOURS)
    result = await db.execute(
        delete(OAuthClient).where(
            OAuthClient.registered_by_user_id.is_(None),
            OAuthClient.created_at < cutoff,
        )
    )
    return result.rowcount or 0


async def prune_audit_log(db: AsyncSession) -> int:
    """Delete MCP audit log rows older than 30 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    result = await db.execute(
        delete(McpAuditLog).where(McpAuditLog.called_at < cutoff)
    )
    return result.rowcount or 0


async def run_once() -> None:
    async with async_session_maker() as db:
        orphans = await prune_orphan_clients(db)
        logs = await prune_audit_log(db)
        await db.commit()
        logger.info("oauth_cleanup: pruned %d orphan clients + %d audit rows", orphans, logs)


if __name__ == "__main__":
    asyncio.run(run_once())
```

- [ ] **Step 3: Schedule on startup**

In `backend/app/main.py` — add at app-startup:

```python
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.jobs.oauth_cleanup import run_once as oauth_cleanup_run_once

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app):
    # existing startup
    scheduler.add_job(oauth_cleanup_run_once, "cron", hour=3, minute=15, id="oauth_cleanup")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)

# Wire lifespan into FastAPI(app = FastAPI(lifespan=lifespan))
```

(If APScheduler isn't already a dependency: `cd backend && uv add apscheduler`.)

- [ ] **Step 4: Run + commit**

```bash
cd backend && uv run pytest tests/test_oauth_cleanup_job.py -v  # PASS
git add backend/app/jobs/ backend/app/main.py backend/pyproject.toml backend/uv.lock backend/tests/test_oauth_cleanup_job.py
git commit -m "feat(jobs): daily cron — orphan DCR clients + 30-day audit log retention"
```

---

## Task 4.5 — `mcp_active_connections` gauge refresher

**Files:**
- Modify: `backend/app/jobs/oauth_cleanup.py` (add `refresh_active_connections_gauge`)
- Modify: `backend/app/main.py` (schedule every 60s)

- [ ] **Step 1: Add gauge refresher**

Append to `backend/app/jobs/oauth_cleanup.py`:

```python
from sqlalchemy import func, select
from app.metrics.registry import mcp_active_connections
from app.oauth.models import OAuthAccessToken


async def refresh_active_connections_gauge() -> None:
    async with async_session_maker() as db:
        now = datetime.now(timezone.utc)
        count = (await db.execute(
            select(func.count(OAuthAccessToken.id)).where(
                OAuthAccessToken.revoked_at.is_(None),
                OAuthAccessToken.expires_at > now,
            )
        )).scalar_one()
        mcp_active_connections.set(count)
```

- [ ] **Step 2: Schedule**

```python
# main.py lifespan
scheduler.add_job(refresh_active_connections_gauge, "interval", seconds=60, id="active_conn_gauge")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/jobs/oauth_cleanup.py backend/app/main.py
git commit -m "feat(metrics): mcp_active_connections gauge refreshed every 60s"
```

---

## End of Phase 4 — Checklist

- [ ] Dashboard shows "Connect your editor" CTA when no OAuth clients connected
- [ ] Modal has 5 client tabs with correct instructions
- [ ] Deep-link button fires `claude://add-connector?url=...`
- [ ] Copy-URL button copies to clipboard
- [ ] `docs/connect/*.md` files exist and are linked
- [ ] `/metrics` returns Prometheus format with all 4 counters + 1 gauge
- [ ] Cron registered: oauth_cleanup at 03:15 daily, gauge refresh every 60s
- [ ] `prune_orphan_clients` + `prune_audit_log` unit tests PASS
- [ ] Full test suite green: `uv run pytest -q && pnpm test`

Proceed to Phase 5 (production rollout).
