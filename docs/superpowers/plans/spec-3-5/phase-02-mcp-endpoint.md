# Phase 2 — MCP Streamable HTTP Endpoint + Tool Dispatcher

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Expose `/mcp` as a spec-2025-06-compliant MCP Streamable HTTP endpoint, authenticated by the Phase 1 JWT. Dispatch all 17 remote vibecell tools against backend services (no HTTP self-calls). Write every tool call to `mcp_audit_log`. At end of phase, a curl request with a Phase-1-issued access token can `initialize`, `tools/list` (17 tools), and `tools/call` on each.

**Architecture:** New package `backend/app/mcp/` with 4 files: `auth.py` (bearer middleware → MCPContext), `server.py` (the `/mcp` endpoint + JSON-RPC dispatch), `tools.py` (tool registry + handlers), `audit.py` (fire-and-forget audit-log writer). Handlers import existing services (`ProjectService`, `SessionService`, etc.) and call them directly. One Alembic migration `0006_mcp_audit_log`.

**Tech Stack:** FastAPI, Pydantic v2, existing service layer from Spec 1 + 2.

**Prerequisite:** Phase 1 complete.

---

## File structure produced by this phase

```
backend/
├── app/
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── auth.py                # Bearer JWT middleware → MCPContext dependency
│   │   ├── audit.py               # AuditLogger with async fire-and-forget
│   │   ├── server.py              # POST /mcp handler + JSON-RPC dispatch
│   │   ├── tools.py               # Tool registry + Pydantic arg schemas
│   │   └── handlers/
│   │       ├── __init__.py
│   │       ├── read.py            # ping, active, list, get, brief, search, recent_projects, claude_md, handover
│   │       ├── write.py           # switch, log_session, update_context, decision, idea, note_append, ship, status
│   │       └── render.py          # claude_md + handover render logic (ports cli render_claude_md / render_handover)
│   └── main.py                    # (modify) mount mcp.server router
├── alembic/versions/
│   └── 0006_mcp_audit_log.py
└── tests/
    ├── test_mcp_auth.py
    ├── test_mcp_server.py
    ├── test_mcp_tools_list.py
    ├── test_mcp_audit.py
    └── test_mcp_tools/
        ├── __init__.py
        ├── test_ping.py
        ├── test_active.py
        ├── test_list.py
        ├── test_get.py
        ├── test_brief.py
        ├── test_search.py
        ├── test_recent_projects.py
        ├── test_switch.py
        ├── test_log_session.py
        ├── test_update_context.py
        ├── test_decision.py
        ├── test_idea.py
        ├── test_note_append.py
        ├── test_ship.py
        ├── test_status.py
        ├── test_claude_md.py
        ├── test_handover.py
        └── test_run_absent.py     # verify vibecell.run is NOT in the registry
```

---

## Task 2.1 — MCP audit log migration + model

**Files:**
- Create: `backend/alembic/versions/0006_mcp_audit_log.py`
- Create: `backend/app/mcp/__init__.py`
- Create: `backend/app/mcp/audit.py` (model only in this task)
- Create: `backend/tests/test_mcp_audit.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_mcp_audit.py
from datetime import datetime, timezone

from sqlalchemy import select

from app.mcp.audit import McpAuditLog, log_tool_call


async def test_audit_insert_roundtrip(async_session) -> None:
    await log_tool_call(
        db=async_session,
        client_id="dyn_abc",
        workspace_id="01WSP",
        user_id="01USR",
        tool_name="vibecell.idea",
        duration_ms=12,
        status="ok",
    )
    await async_session.flush()
    got = (await async_session.execute(select(McpAuditLog))).scalars().all()
    assert len(got) == 1
    assert got[0].tool_name == "vibecell.idea"
    assert got[0].status == "ok"
    assert got[0].duration_ms == 12
```

- [ ] **Step 2: Create migration**

```python
# backend/alembic/versions/0006_mcp_audit_log.py
"""mcp audit log

Revision ID: 0006_mcp_audit_log
Revises: 0005_oauth
Create Date: 2026-04-20 00:00:01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_mcp_audit_log"
down_revision = "0005_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_audit_log",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("client_id", sa.String(64), sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False),
    )
    op.create_index("ix_mcp_audit_client_called", "mcp_audit_log", ["client_id", "called_at"])
    op.create_index("ix_mcp_audit_workspace_tool", "mcp_audit_log", ["workspace_id", "tool_name"])


def downgrade() -> None:
    op.drop_table("mcp_audit_log")
```

- [ ] **Step 3: Create audit module**

```python
# backend/app/mcp/__init__.py   (empty)
```

```python
# backend/app/mcp/audit.py
"""MCP tool-call audit logging. Write-only at call-site; Connections UI reads aggregated."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ulid import new_ulid


class McpAuditLog(Base):
    __tablename__ = "mcp_audit_log"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("oauth_clients.client_id", ondelete="CASCADE"))
    workspace_id: Mapped[str] = mapped_column(String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id", ondelete="CASCADE"))
    tool_name: Mapped[str] = mapped_column(String(64))
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16))   # "ok" | "error" | "denied"


async def log_tool_call(
    db: AsyncSession, *, client_id: str, workspace_id: str, user_id: str,
    tool_name: str, duration_ms: int, status: str,
) -> None:
    db.add(McpAuditLog(
        id=new_ulid(),
        client_id=client_id,
        workspace_id=workspace_id,
        user_id=user_id,
        tool_name=tool_name,
        called_at=datetime.now(timezone.utc),
        duration_ms=duration_ms,
        status=status,
    ))
```

- [ ] **Step 4: Apply migration + run test**

```bash
cd backend && uv run alembic upgrade head
cd backend && uv run pytest tests/test_mcp_audit.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0006_mcp_audit_log.py backend/app/mcp/__init__.py backend/app/mcp/audit.py backend/tests/test_mcp_audit.py
git commit -m "feat(mcp): audit-log table + insertion helper"
```

---

## Task 2.2 — Bearer-JWT auth middleware → `MCPContext`

**Files:**
- Create: `backend/app/mcp/auth.py`
- Create: `backend/tests/test_mcp_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_mcp_auth.py
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.mcp.auth import MCPContext, require_mcp_context
from app.oauth.tokens import JTIBlacklist, OAuthTokenClaims, issue_access_token


def _build_probe_app():
    app = FastAPI()

    @app.get("/probe")
    async def probe(ctx: MCPContext = Depends(require_mcp_context)):
        return {"user": ctx.user_id, "workspace": ctx.workspace_id, "client": ctx.client_id}

    return app


def test_probe_requires_bearer():
    with TestClient(_build_probe_app()) as c:
        r = c.get("/probe")
        assert r.status_code == 401
        assert "resource_metadata" in r.headers["www-authenticate"]


def test_probe_rejects_garbage_token():
    with TestClient(_build_probe_app()) as c:
        r = c.get("/probe", headers={"Authorization": "Bearer garbage"})
        assert r.status_code == 401


def test_probe_rejects_expired(monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "OAUTH_ACCESS_TOKEN_TTL_SECONDS", -10)
    tok, _ = issue_access_token(OAuthTokenClaims(sub="u", client_id="c", workspace_id="w", scope="vibecell:tools"))
    with TestClient(_build_probe_app()) as c:
        r = c.get("/probe", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401


async def test_probe_rejects_revoked_jti():
    tok, jti = issue_access_token(OAuthTokenClaims(sub="u", client_id="c", workspace_id="w", scope="vibecell:tools"))
    await JTIBlacklist().add(jti, ttl_seconds=60)
    with TestClient(_build_probe_app()) as c:
        r = c.get("/probe", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401


def test_probe_rejects_wrong_scope():
    tok, _ = issue_access_token(OAuthTokenClaims(sub="u", client_id="c", workspace_id="w", scope="other"))
    with TestClient(_build_probe_app()) as c:
        r = c.get("/probe", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 403


def test_probe_accepts_valid():
    tok, _ = issue_access_token(OAuthTokenClaims(sub="u1", client_id="c1", workspace_id="w1", scope="vibecell:tools"))
    with TestClient(_build_probe_app()) as c:
        r = c.get("/probe", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert r.json() == {"user": "u1", "workspace": "w1", "client": "c1"}
```

- [ ] **Step 2: Write implementation**

```python
# backend/app/mcp/auth.py
"""Bearer-JWT middleware for the /mcp endpoint. Yields an MCPContext.

On failure, returns 401 with WWW-Authenticate pointing at the protected-resource metadata
(required by MCP clients to auto-start the OAuth dance).
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.oauth.tokens import JTIBlacklist, verify_access_token


_METADATA_URL = "https://vibecell.dev/.well-known/oauth-protected-resource"
_WWW_AUTH_HEADER = {"WWW-Authenticate": f'Bearer resource_metadata="{_METADATA_URL}"'}


@dataclass(frozen=True, slots=True)
class MCPContext:
    db: AsyncSession
    user_id: str
    workspace_id: str
    client_id: str
    jti: str
    scope: str


async def require_mcp_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MCPContext:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer", headers=_WWW_AUTH_HEADER)

    token = header[7:].strip()
    try:
        claims = verify_access_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid_token", headers=_WWW_AUTH_HEADER)

    if await JTIBlacklist().is_revoked(claims.jti):
        raise HTTPException(status_code=401, detail="revoked_token", headers=_WWW_AUTH_HEADER)

    if "vibecell:tools" not in claims.scope.split():
        raise HTTPException(status_code=403, detail="insufficient_scope", headers=_WWW_AUTH_HEADER)

    return MCPContext(
        db=db,
        user_id=claims.sub,
        workspace_id=claims.workspace_id,
        client_id=claims.client_id,
        jti=claims.jti,
        scope=claims.scope,
    )
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_mcp_auth.py -v`
Expected: All 6 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/mcp/auth.py backend/tests/test_mcp_auth.py
git commit -m "feat(mcp): bearer-JWT middleware → MCPContext dependency"
```

---

## Task 2.3 — Tool registry

**Files:**
- Create: `backend/app/mcp/tools.py`
- Create: `backend/app/mcp/handlers/__init__.py`
- Create: `backend/app/mcp/handlers/read.py` (stub handlers returning `{}`)
- Create: `backend/app/mcp/handlers/write.py` (stub handlers returning `{}`)
- Create: `backend/tests/test_mcp_tools/__init__.py`
- Create: `backend/tests/test_mcp_tools/test_run_absent.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_mcp_tools/test_run_absent.py
from app.mcp.tools import TOOLS, TOOLS_BY_NAME


def test_exactly_17_tools_registered() -> None:
    assert len(TOOLS) == 17


def test_vibecell_run_is_absent() -> None:
    assert "vibecell.run" not in TOOLS_BY_NAME
    names = [t.name for t in TOOLS]
    assert "vibecell.run" not in names


def test_all_expected_tools_present() -> None:
    expected = {
        "vibecell.ping", "vibecell.active", "vibecell.list", "vibecell.get",
        "vibecell.brief", "vibecell.search", "vibecell.recent_projects", "vibecell.switch",
        "vibecell.log_session", "vibecell.update_context", "vibecell.decision",
        "vibecell.idea", "vibecell.note_append", "vibecell.ship", "vibecell.status",
        "vibecell.claude_md", "vibecell.handover",
    }
    actual = {t.name for t in TOOLS}
    assert actual == expected
```

- [ ] **Step 2: Implement registry with Pydantic schemas + stub handlers**

```python
# backend/app/mcp/tools.py
"""MCP tool registry — 17 tools (vibecell.run excluded)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from pydantic import BaseModel, Field

from app.mcp.auth import MCPContext
from app.mcp.handlers import read as r
from app.mcp.handlers import write as w


# -------- Argument schemas --------

class NoArgs(BaseModel):
    pass


class SlugArg(BaseModel):
    slug: str | None = None


class SlugRequired(BaseModel):
    slug: str


class ListArgs(BaseModel):
    status: str | None = None
    tag: str | None = None
    q: str | None = None


class SearchArgs(BaseModel):
    q: str
    limit: int = 50


class RecentArgs(BaseModel):
    n: int = 5


class LogSessionArgs(BaseModel):
    summary: str
    files_touched: list[str] = Field(default_factory=list)
    commits: list[dict] = Field(default_factory=list)
    next_step: str | None = None


class UpdateContextArgs(BaseModel):
    current_focus: str | None = None
    next_step: str | None = None
    user_wants: str | None = None
    open_questions: list[str] | None = None
    known_issues: list[str] | None = None
    blocked_by: str | None = None


class DecisionArgs(BaseModel):
    title: str
    decision: str
    context: str | None = None
    consequences: str | None = None
    reconsider_if: str | None = None


class IdeaArgs(BaseModel):
    body: str
    project: str | None = None


class NoteAppendArgs(BaseModel):
    markdown: str


class ShipArgs(BaseModel):
    version: str | None = None
    summary: str | None = None
    changelog_md: str | None = None


class StatusArgs(BaseModel):
    status: str


# -------- Registry --------

Handler = Callable[[BaseModel, MCPContext], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    args_schema: type[BaseModel]
    handler: Handler


TOOLS: list[Tool] = [
    # Read
    Tool("vibecell.ping", "Health check. Returns ok=true + version + active project slug.", NoArgs, r.handle_ping),
    Tool("vibecell.active", "Return the currently-active project's full aggregate. Always call this at session start.", NoArgs, r.handle_active),
    Tool("vibecell.list", "List projects in the active workspace. Optional filters: status, tag, q.", ListArgs, r.handle_list),
    Tool("vibecell.get", "Return the full aggregate for a single project by slug.", SlugRequired, r.handle_get),
    Tool("vibecell.brief", "Resurrection brief for a project. Defaults to active.", SlugArg, r.handle_brief),
    Tool("vibecell.search", "Federated full-text search across the workspace.", SearchArgs, r.handle_search),
    Tool("vibecell.recent_projects", "Return up to n projects ordered by sidebar position.", RecentArgs, r.handle_recent),
    Tool("vibecell.claude_md", "Generate a CLAUDE.md-ready markdown brief for a project.", SlugArg, r.handle_claude_md),
    Tool("vibecell.handover", "Longer prose onboarding brief. Defaults to active.", SlugArg, r.handle_handover),
    # Write
    Tool("vibecell.switch", "Switch the active project within this workspace.", SlugRequired, w.handle_switch),
    Tool("vibecell.log_session", "Log a coding session.", LogSessionArgs, w.handle_log_session),
    Tool("vibecell.update_context", "Patch the active project's context fields.", UpdateContextArgs, w.handle_update_context),
    Tool("vibecell.decision", "Record an ADR-lite decision on the active project.", DecisionArgs, w.handle_decision),
    Tool("vibecell.idea", "Capture an idea. Workspace inbox if project omitted.", IdeaArgs, w.handle_idea),
    Tool("vibecell.note_append", "Append a markdown block to the active project's notes.", NoteAppendArgs, w.handle_note_append),
    Tool("vibecell.ship", "Record a ship event for the active project.", ShipArgs, w.handle_ship),
    Tool("vibecell.status", "Set the active project's status.", StatusArgs, w.handle_status),
]

TOOLS_BY_NAME: dict[str, Tool] = {t.name: t for t in TOOLS}
```

- [ ] **Step 3: Create handler stubs**

```python
# backend/app/mcp/handlers/__init__.py (empty)
```

```python
# backend/app/mcp/handlers/read.py
"""MCP read handlers. All take the Pydantic args model + MCPContext, return JSON string."""
from __future__ import annotations

import json

from app.mcp.auth import MCPContext


async def handle_ping(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return json.dumps({"ok": True, "version": "0.1.0", "active_slug": None})


async def handle_active(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return json.dumps({})


async def handle_list(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return json.dumps([])


async def handle_get(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return json.dumps({})


async def handle_brief(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return ""


async def handle_search(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return json.dumps({"results": []})


async def handle_recent(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return json.dumps([])


async def handle_claude_md(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return ""


async def handle_handover(args, ctx: MCPContext) -> str:  # noqa: ARG001
    return ""
```

```python
# backend/app/mcp/handlers/write.py
"""MCP write handler stubs. Real implementations in Tasks 2.6+."""
from __future__ import annotations

import json

from app.mcp.auth import MCPContext


async def handle_switch(args, ctx: MCPContext) -> str: return json.dumps({})  # noqa
async def handle_log_session(args, ctx: MCPContext) -> str: return json.dumps({})
async def handle_update_context(args, ctx: MCPContext) -> str: return json.dumps({})
async def handle_decision(args, ctx: MCPContext) -> str: return json.dumps({})
async def handle_idea(args, ctx: MCPContext) -> str: return json.dumps({})
async def handle_note_append(args, ctx: MCPContext) -> str: return json.dumps({})
async def handle_ship(args, ctx: MCPContext) -> str: return json.dumps({})
async def handle_status(args, ctx: MCPContext) -> str: return json.dumps({})
```

- [ ] **Step 4: Run the test**

Run: `cd backend && uv run pytest tests/test_mcp_tools/test_run_absent.py -v`
Expected: All 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/mcp/tools.py backend/app/mcp/handlers/ backend/tests/test_mcp_tools/
git commit -m "feat(mcp): tool registry with 17 entries + stub handlers (vibecell.run excluded)"
```

---

## Task 2.4 — `/mcp` endpoint + JSON-RPC dispatch

**Files:**
- Create: `backend/app/mcp/server.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_mcp_server.py`
- Create: `backend/tests/test_mcp_tools_list.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_mcp_server.py
async def test_mcp_requires_auth(client) -> None:
    resp = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert resp.status_code == 401


async def test_initialize_returns_server_info(mcp_client) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    assert body["result"]["protocolVersion"] == "2025-06-18"
    assert body["result"]["serverInfo"]["name"] == "vibecell"
    assert body["result"]["capabilities"]["tools"] == {}


async def test_ping_method(mcp_client) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 7, "method": "ping", "params": {},
    })
    assert resp.status_code == 200
    assert resp.json()["result"] == {}


async def test_unknown_method(mcp_client) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 8, "method": "not_a_method", "params": {},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"]["code"] == -32601
```

```python
# backend/tests/test_mcp_tools_list.py
async def test_tools_list_returns_all_17(mcp_client) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    })
    assert resp.status_code == 200
    tools = resp.json()["result"]["tools"]
    assert len(tools) == 17
    names = {t["name"] for t in tools}
    assert "vibecell.ping" in names
    assert "vibecell.run" not in names
    # Each tool has schema + description
    for t in tools:
        assert t["name"].startswith("vibecell.")
        assert isinstance(t["description"], str)
        assert "inputSchema" in t
```

- [ ] **Step 2: Implement server**

```python
# backend/app/mcp/server.py
"""MCP Streamable HTTP endpoint — single POST /mcp with JSON-RPC dispatch.

Spec: MCP 2025-06 (Streamable HTTP transport).
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError

from app.mcp.audit import log_tool_call
from app.mcp.auth import MCPContext, require_mcp_context
from app.mcp.tools import TOOLS, TOOLS_BY_NAME


router = APIRouter()


def _ok(id_: int | str | None, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: int | str | None, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


@router.post("/mcp")
async def mcp_endpoint(
    request: Request,
    ctx: MCPContext = Depends(require_mcp_context),
) -> dict:
    body = await request.json()
    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}

    if method == "initialize":
        return _ok(req_id, {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "vibecell", "version": "0.1.0"},
        })

    if method == "ping":
        return _ok(req_id, {})

    if method == "tools/list":
        tools_out = []
        for t in TOOLS:
            tools_out.append({
                "name": t.name,
                "description": t.description,
                "inputSchema": t.args_schema.model_json_schema(),
            })
        return _ok(req_id, {"tools": tools_out})

    if method == "tools/call":
        return await _dispatch_tool_call(ctx, req_id, params)

    return _err(req_id, -32601, f"Method not found: {method}")


async def _dispatch_tool_call(ctx: MCPContext, req_id, params: dict) -> dict:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    tool = TOOLS_BY_NAME.get(name or "")
    if tool is None:
        return _err(req_id, -32602, f"Unknown tool: {name}")

    try:
        args_model = tool.args_schema.model_validate(arguments)
    except ValidationError as e:
        return _err(req_id, -32602, f"Invalid arguments: {e.errors()}")

    t0 = time.monotonic()
    try:
        text = await tool.handler(args_model, ctx)
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        await log_tool_call(
            db=ctx.db, client_id=ctx.client_id, workspace_id=ctx.workspace_id, user_id=ctx.user_id,
            tool_name=name, duration_ms=int((time.monotonic() - t0) * 1000), status="error",
        )
        return _err(req_id, -32603, f"Internal error: {type(exc).__name__}")

    await log_tool_call(
        db=ctx.db, client_id=ctx.client_id, workspace_id=ctx.workspace_id, user_id=ctx.user_id,
        tool_name=name, duration_ms=int((time.monotonic() - t0) * 1000), status=status,
    )
    return _ok(req_id, {"content": [{"type": "text", "text": text}]})
```

- [ ] **Step 3: Mount in `main.py`**

```python
from app.mcp.server import router as mcp_router
app.include_router(mcp_router)
```

- [ ] **Step 4: Add `mcp_client` fixture**

```python
# backend/tests/conftest.py (addition)
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def mcp_client(client, issued_token_pair) -> AsyncClient:
    token = issued_token_pair["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    yield client
    client.headers.pop("Authorization", None)
```

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_mcp_server.py tests/test_mcp_tools_list.py -v`
Expected: All 6 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/mcp/server.py backend/app/main.py backend/tests/test_mcp_server.py backend/tests/test_mcp_tools_list.py backend/tests/conftest.py
git commit -m "feat(mcp): POST /mcp — Streamable HTTP endpoint + JSON-RPC dispatch (initialize, ping, tools/list, tools/call)"
```

---

## Task 2.5 — Wire `read` handlers to services (9 tools)

**Files:**
- Modify: `backend/app/mcp/handlers/read.py`
- Create: `backend/app/mcp/handlers/render.py` (claude_md + handover, ported from Rust)
- Create: test files `backend/tests/test_mcp_tools/test_{ping,active,list,get,brief,search,recent_projects,claude_md,handover}.py`

One task per tool follows the TDD pattern. Show full detail for `active`, `list`, `search`, `claude_md`; the rest follow the same shape.

### 2.5.a — `vibecell.ping`

- [ ] **Step 1: Test**

```python
# backend/tests/test_mcp_tools/test_ping.py
async def test_ping_returns_active_slug(mcp_client, user_workspace_with_active_project) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.ping", "arguments": {}},
    })
    text = resp.json()["result"]["content"][0]["text"]
    import json
    data = json.loads(text)
    assert data["ok"] is True
    assert data["version"]
    assert "active_slug" in data
```

- [ ] **Step 2: Implementation**

Replace the `handle_ping` stub:

```python
# backend/app/mcp/handlers/read.py (replace stub)
from app.services.projects import ProjectService


async def handle_ping(args, ctx: MCPContext) -> str:
    svc = ProjectService(ctx.db)
    active_slug = await svc.get_active_slug(ctx.workspace_id, ctx.user_id)
    return json.dumps({"ok": True, "version": "0.1.0", "active_slug": active_slug})
```

- [ ] **Step 3: Run & commit**

```bash
cd backend && uv run pytest tests/test_mcp_tools/test_ping.py -v  # PASS
git add backend/app/mcp/handlers/read.py backend/tests/test_mcp_tools/test_ping.py
git commit -m "feat(mcp): wire vibecell.ping to ProjectService.get_active_slug"
```

### 2.5.b — `vibecell.active`

- [ ] **Step 1: Test**

```python
# backend/tests/test_mcp_tools/test_active.py
async def test_active_returns_project_aggregate(mcp_client, user_workspace_with_active_project) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.active", "arguments": {}},
    })
    import json
    data = json.loads(resp.json()["result"]["content"][0]["text"])
    assert data["slug"]
    assert data["name"]
    assert "context" in data


async def test_active_errors_when_no_active_project(mcp_client_no_active_project) -> None:
    resp = await mcp_client_no_active_project.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.active", "arguments": {}},
    })
    assert resp.json().get("error", {}).get("code") == -32603
```

- [ ] **Step 2: Implementation**

```python
# backend/app/mcp/handlers/read.py (replace stub)
async def handle_active(args, ctx: MCPContext) -> str:
    svc = ProjectService(ctx.db)
    slug = await svc.get_active_slug(ctx.workspace_id, ctx.user_id)
    if slug is None:
        raise RuntimeError("No active project in this workspace")
    agg = await svc.get_aggregate(ctx.workspace_id, slug)
    return json.dumps(agg)
```

- [ ] **Step 3: Run & commit**

### 2.5.c — `vibecell.list`

- [ ] **Test:**

```python
# backend/tests/test_mcp_tools/test_list.py
async def test_list_returns_array(mcp_client, user_workspace_with_active_project) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.list", "arguments": {}},
    })
    import json
    data = json.loads(resp.json()["result"]["content"][0]["text"])
    assert isinstance(data, list)
    assert any(p["slug"] == "vibecell" for p in data)


async def test_list_filters_by_status(mcp_client, user_workspace_with_active_project) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.list", "arguments": {"status": "live"}},
    })
    import json
    data = json.loads(resp.json()["result"]["content"][0]["text"])
    assert all(p["status"] == "live" for p in data)
```

- [ ] **Implementation:**

```python
async def handle_list(args, ctx: MCPContext) -> str:
    svc = ProjectService(ctx.db)
    rows = await svc.list(
        workspace_id=ctx.workspace_id, status=args.status, tag=args.tag, q=args.q, limit=200,
    )
    return json.dumps([_serialize_project_summary(r) for r in rows])


def _serialize_project_summary(p) -> dict:
    return {
        "id": p.id, "slug": p.slug, "name": p.name, "status": p.status,
        "pitch": p.pitch, "emoji": p.emoji, "position": p.position,
    }
```

- [ ] **Commit.**

### 2.5.d — `vibecell.get`

- [ ] **Test:**

```python
# backend/tests/test_mcp_tools/test_get.py
async def test_get_returns_aggregate(mcp_client, user_workspace_with_active_project) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.get", "arguments": {"slug": "vibecell"}},
    })
    import json
    data = json.loads(resp.json()["result"]["content"][0]["text"])
    assert data["slug"] == "vibecell"
    assert data["name"]


async def test_get_missing_slug_returns_error(mcp_client) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.get", "arguments": {}},
    })
    assert "error" in resp.json()
```

- [ ] **Implementation:**

```python
async def handle_get(args, ctx: MCPContext) -> str:
    svc = ProjectService(ctx.db)
    agg = await svc.get_aggregate(ctx.workspace_id, args.slug)
    return json.dumps(agg)
```

- [ ] **Commit.**

### 2.5.e — `vibecell.brief`

- [ ] **Test:**

```python
# backend/tests/test_mcp_tools/test_brief.py
async def test_brief_prose_mentions_name(mcp_client, user_workspace_with_active_project) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.brief", "arguments": {"slug": "vibecell"}},
    })
    text = resp.json()["result"]["content"][0]["text"]
    assert "Vibecell" in text
    assert "Suggested first move" in text
```

- [ ] **Implementation:** copy `render_brief` logic from `cli/src/daemon/tools.rs` — port the Python version using the fields of the aggregate. (See `backend/app/mcp/handlers/render.py` file scaffolded in Task 2.5.h below.)

- [ ] **Commit.**

### 2.5.f — `vibecell.search`

- [ ] **Test:**

```python
# backend/tests/test_mcp_tools/test_search.py
async def test_search_returns_results(mcp_client, user_workspace_with_active_project) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.search", "arguments": {"q": "vibecell"}},
    })
    import json
    data = json.loads(resp.json()["result"]["content"][0]["text"])
    assert "results" in data
    assert isinstance(data["results"], list)
```

- [ ] **Implementation:**

```python
from app.services.search import SearchService

async def handle_search(args, ctx: MCPContext) -> str:
    svc = SearchService(ctx.db)
    hits = await svc.search_all(ctx.workspace_id, args.q, limit=args.limit)
    return json.dumps({"results": hits})
```

- [ ] **Commit.**

### 2.5.g — `vibecell.recent_projects`

- [ ] **Test:**

```python
# backend/tests/test_mcp_tools/test_recent_projects.py
async def test_recent_returns_array_up_to_n(mcp_client, user_workspace_with_two_projects) -> None:
    import json
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.recent_projects", "arguments": {"n": 1}},
    })
    data = json.loads(resp.json()["result"]["content"][0]["text"])
    assert isinstance(data, list)
    assert len(data) == 1
```

- [ ] **Implementation:**

```python
# backend/app/mcp/handlers/read.py (replace stub)
async def handle_recent(args, ctx: MCPContext) -> str:
    svc = ProjectService(ctx.db)
    rows = await svc.list(workspace_id=ctx.workspace_id, limit=200)
    trimmed = rows[: args.n]
    return json.dumps([_serialize_project_summary(r) for r in trimmed])
```

- [ ] **Commit.**

### 2.5.h — `vibecell.claude_md` and `vibecell.handover`

**Files:**
- Create: `backend/app/mcp/handlers/render.py`

Port `render_claude_md` and `render_handover` from `cli/src/daemon/tools.rs`:

```python
# backend/app/mcp/handlers/render.py
"""Render functions ported from cli/src/daemon/tools.rs — claude_md + handover.

These take the project aggregate dict and return markdown/prose. Keep the output
byte-for-byte compatible with the Rust daemon so Claude's prompt-side handling
is identical whether calling local or remote.
"""
from __future__ import annotations

from datetime import datetime, timezone


def render_claude_md(full: dict) -> str:
    name = full.get("name") or "Project"
    pitch = full.get("pitch") or "(no pitch yet)"
    stack = full.get("stack") or []
    infra = full.get("infra") or {}
    ctx = full.get("context") or {}
    links = full.get("links") or []
    commands = full.get("commands") or []

    out = [f"# {name}", "", pitch, ""]

    out.append("## Stack")
    if not stack:
        out.append("- (no stack items recorded)")
    else:
        for s in stack:
            n, k = s.get("name"), s.get("kind")
            out.append(f"- {n} ({k})" if k else f"- {n}")
    out.append("")

    out.append("## Infra")
    any_infra = False
    for field, label in (("server_alias", "Server"), ("domain_primary", "Domain"),
                        ("db_host", "DB"), ("dns_provider", "DNS")):
        if infra.get(field):
            out.append(f"- {label}: {infra[field]}")
            any_infra = True
    if not any_infra:
        out.append("- (no infra recorded)")
    out.append("- Secrets: see `hangar secret list`")
    out.append("")

    out.append("## Current state")
    out.append(f"- Focus: {ctx.get('current_focus') or '(unset)'}")
    out.append(f"- Next: {ctx.get('next_step') or '(unset)'}")
    out.append(f"- User wants: {ctx.get('user_wants') or '(unset)'}")
    oq = ctx.get("open_questions") or []
    if not oq:
        out.append("- Open questions: (none)")
    else:
        out.append("- Open questions:")
        for q in oq:
            out.append(f"  - {q}")
    out.append(f"- Blocked by: {ctx.get('blocked_by') or '(none)'}")
    out.append("")

    out.append("## Links")
    if not links:
        out.append("- (no links recorded)")
    else:
        for l in links:
            kind = l.get("kind") or "link"
            label = l.get("label") or kind
            url = l.get("url")
            if url:
                out.append(f"- [{kind}] {label} — {url}")
    out.append("")

    out.append("## Commands")
    if not commands:
        out.append("- (no commands saved — add one with `hangar set-command`)")
    else:
        for c in commands:
            if c.get("label") and c.get("command"):
                out.append(f"- {c['label']}: `{c['command']}`")
    out.append("")

    out.append(f"Generated by Vibecell 0.1.0 on {datetime.now(timezone.utc).isoformat()}.")
    return "\n".join(out) + "\n"


def render_handover(full: dict) -> str:
    name = full.get("name") or "the project"
    pitch = full.get("pitch") or "(no pitch captured yet)"
    status = full.get("status") or "idea"
    ctx = full.get("context") or {}
    current_focus = ctx.get("current_focus") or ""
    next_step = ctx.get("next_step") or ""
    user_wants = ctx.get("user_wants") or ""
    blocked_by = ctx.get("blocked_by") or ""
    open_q = ctx.get("open_questions") or []
    known_issues = ctx.get("known_issues") or []
    commands = full.get("commands") or []

    parts: list[str] = [f"{name} — {pitch}.\n"]

    parts.append(f"Status: **{status}**. ")
    parts.append(f"Current focus is *{current_focus}*. " if current_focus else "No explicit focus is recorded. ")
    if user_wants:
        parts.append(f"The user wants: {user_wants}. ")
    parts.append("\n\n")

    if not known_issues:
        parts.append("No known issues logged.\n\n")
    else:
        parts.append("Known issues:\n")
        for k in known_issues:
            parts.append(f"- {k}\n")
        parts.append("\n")

    if next_step:
        parts.append(f"**What you were about to do:** {next_step}. ")
    else:
        parts.append("**What you were about to do:** not recorded. ")
    if blocked_by and blocked_by != "(none)":
        parts.append(f"(Blocked by: {blocked_by}.) ")
    parts.append("\n\n")

    if open_q:
        parts.append("Open questions:\n")
        for q in open_q:
            parts.append(f"- {q}\n")
        parts.append("\n")

    parts.append("**Suggested first move:** ")
    if next_step:
        suggestion = f"pick up where you left off — {next_step}"
    elif current_focus:
        suggestion = f"continue current focus ({current_focus})"
    elif commands:
        suggestion = "browse saved commands with `hangar run <label>`, then call `vibecell.update_context` to set a focus"
    else:
        suggestion = "call `vibecell.update_context` to set current_focus + next_step"
    parts.append(suggestion + ".\n")
    return "".join(parts)
```

Wire into handlers:

```python
# backend/app/mcp/handlers/read.py (replace stubs)
from app.mcp.handlers.render import render_claude_md, render_handover

async def handle_claude_md(args, ctx: MCPContext) -> str:
    svc = ProjectService(ctx.db)
    slug = args.slug or await svc.get_active_slug(ctx.workspace_id, ctx.user_id)
    if slug is None:
        raise RuntimeError("No active project — pass `slug`")
    agg = await svc.get_aggregate(ctx.workspace_id, slug)
    return render_claude_md(agg)


async def handle_handover(args, ctx: MCPContext) -> str:
    svc = ProjectService(ctx.db)
    slug = args.slug or await svc.get_active_slug(ctx.workspace_id, ctx.user_id)
    if slug is None:
        raise RuntimeError("No active project — pass `slug`")
    agg = await svc.get_aggregate(ctx.workspace_id, slug)
    return render_handover(agg)
```

Tests:

```python
# backend/tests/test_mcp_tools/test_claude_md.py
async def test_claude_md_contains_sections(mcp_client, user_workspace_with_active_project) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.claude_md", "arguments": {"slug": "vibecell"}},
    })
    text = resp.json()["result"]["content"][0]["text"]
    assert "## Stack" in text
    assert "## Infra" in text
    assert "## Current state" in text
    assert "## Links" in text
    assert "## Commands" in text
    assert "Generated by Vibecell" in text
```

```python
# backend/tests/test_mcp_tools/test_handover.py
async def test_handover_prose(mcp_client, user_workspace_with_active_project) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.handover", "arguments": {"slug": "vibecell"}},
    })
    text = resp.json()["result"]["content"][0]["text"]
    assert "Status:" in text
    assert "Suggested first move" in text
```

- [ ] **Run each read-handler test + commit each separately** (9 commits total — one per tool). Use message pattern:

```bash
git commit -m "feat(mcp): wire vibecell.<name> handler"
```

---

## Task 2.6 — Wire `write` handlers (8 tools)

Same pattern as 2.5. One task per write tool.

### 2.6.a — `vibecell.switch`

- [ ] **Test:**

```python
# backend/tests/test_mcp_tools/test_switch.py
async def test_switch_sets_active_project(mcp_client, user_workspace_with_two_projects) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.switch", "arguments": {"slug": "other"}},
    })
    assert resp.status_code == 200
    # verify via ping
    ping = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "vibecell.ping", "arguments": {}},
    })
    import json
    data = json.loads(ping.json()["result"]["content"][0]["text"])
    assert data["active_slug"] == "other"
```

- [ ] **Implementation:**

```python
# backend/app/mcp/handlers/write.py (replace stubs)
from app.services.projects import ProjectService

async def handle_switch(args, ctx):
    svc = ProjectService(ctx.db)
    await svc.set_active(ctx.workspace_id, ctx.user_id, args.slug)
    return json.dumps({"active_slug": args.slug})
```

- [ ] **Commit.**

### 2.6.b — `vibecell.log_session`

- [ ] **Test:**

```python
# backend/tests/test_mcp_tools/test_log_session.py
async def test_log_session_persists(mcp_client, user_workspace_with_active_project) -> None:
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.log_session", "arguments": {
            "summary": "Shipped MCP handler", "next_step": "rollout",
            "files_touched": ["a.py", "b.py"], "commits": [{"sha": "abc", "msg": "x"}],
        }},
    })
    import json
    data = json.loads(resp.json()["result"]["content"][0]["text"])
    assert data["id"]
    assert data["summary"] == "Shipped MCP handler"
```

- [ ] **Implementation:**

```python
from datetime import datetime, timezone
from app.services.sessions import SessionService

async def handle_log_session(args, ctx):
    svc = SessionService(ctx.db)
    slug = await ProjectService(ctx.db).get_active_slug(ctx.workspace_id, ctx.user_id)
    if slug is None:
        raise RuntimeError("No active project")
    now = datetime.now(timezone.utc)
    sess = await svc.create(
        workspace_id=ctx.workspace_id, project_slug=slug, user_id=ctx.user_id,
        started_at=now, ended_at=now, summary=args.summary, next_step=args.next_step,
        files_touched=args.files_touched, commits=args.commits, source="skill",
    )
    return json.dumps({"id": sess.id, "summary": sess.summary, "next_step": sess.next_step})
```

- [ ] **Commit.**

### 2.6.c — `vibecell.update_context`

- [ ] **Test:**

```python
# backend/tests/test_mcp_tools/test_update_context.py
async def test_update_context_patches_fields(mcp_client, user_workspace_with_active_project, async_session) -> None:
    import json
    from app.services.projects import ProjectService
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.update_context", "arguments": {
            "current_focus": "shipping MCP",
            "next_step": "rollout",
            "open_questions": ["v0.4 changelog?"],
        }},
    })
    assert resp.status_code == 200
    # Verify via ProjectService aggregate
    svc = ProjectService(async_session)
    agg = await svc.get_aggregate(user_workspace_with_active_project["workspace"].id, "vibecell")
    assert agg["context"]["current_focus"] == "shipping MCP"
    assert agg["context"]["next_step"] == "rollout"
    assert "v0.4 changelog?" in agg["context"]["open_questions"]
```

- [ ] **Implementation:**

```python
# backend/app/mcp/handlers/write.py (replace stub)
async def handle_update_context(args, ctx):
    svc = ProjectService(ctx.db)
    slug = await svc.get_active_slug(ctx.workspace_id, ctx.user_id)
    if slug is None:
        raise RuntimeError("No active project")
    patch = args.model_dump(exclude_none=True)
    updated = await svc.patch_context(ctx.workspace_id, slug, patch)
    return json.dumps(updated)
```

- [ ] **Commit.**

### 2.6.d — `vibecell.decision`

- [ ] **Test:**

```python
# backend/tests/test_mcp_tools/test_decision.py
async def test_decision_creates_row(mcp_client, user_workspace_with_active_project) -> None:
    import json
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.decision", "arguments": {
            "title": "Use SQLite for tests",
            "decision": "Pytest-asyncio + in-memory SQLite for unit tests.",
            "context": "Faster feedback loop.",
        }},
    })
    data = json.loads(resp.json()["result"]["content"][0]["text"])
    assert data["id"]
    assert data["title"] == "Use SQLite for tests"
```

- [ ] **Implementation:**

```python
from app.services.decisions import DecisionService

async def handle_decision(args, ctx):
    slug = await ProjectService(ctx.db).get_active_slug(ctx.workspace_id, ctx.user_id)
    if slug is None:
        raise RuntimeError("No active project")
    svc = DecisionService(ctx.db)
    row = await svc.create(
        workspace_id=ctx.workspace_id, project_slug=slug,
        title=args.title, decision=args.decision,
        context=args.context, consequences=args.consequences,
        reconsider_if=args.reconsider_if,
    )
    return json.dumps({"id": row.id, "title": row.title})
```

- [ ] **Commit.**

### 2.6.e — `vibecell.idea`

- [ ] **Test:**

```python
# backend/tests/test_mcp_tools/test_idea.py
async def test_idea_with_project(mcp_client, user_workspace_with_active_project) -> None:
    import json
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.idea", "arguments": {"body": "Project-scoped idea", "project": "vibecell"}},
    })
    data = json.loads(resp.json()["result"]["content"][0]["text"])
    assert data["id"]
    assert data["body"] == "Project-scoped idea"


async def test_idea_workspace_inbox(mcp_client, user_workspace_with_active_project) -> None:
    import json
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.idea", "arguments": {"body": "Workspace inbox"}},
    })
    data = json.loads(resp.json()["result"]["content"][0]["text"])
    assert data["id"]
    assert data.get("project_id") is None
```

- [ ] **Implementation:**

```python
from app.services.ideas import IdeaService

async def handle_idea(args, ctx):
    svc = IdeaService(ctx.db)
    if args.project:
        row = await svc.create_for_project(
            workspace_id=ctx.workspace_id, project_slug=args.project,
            body=args.body, source="skill",
        )
    else:
        row = await svc.create_workspace_inbox(
            workspace_id=ctx.workspace_id, body=args.body, source="skill",
        )
    return json.dumps({"id": row.id, "body": row.body, "project_id": row.project_id})
```

- [ ] **Commit.**

### 2.6.f — `vibecell.note_append`

- [ ] **Test:**

```python
# backend/tests/test_mcp_tools/test_note_append.py
async def test_note_append_preserves_existing(mcp_client, user_workspace_with_active_project) -> None:
    first = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.note_append", "arguments": {"markdown": "First note."}},
    })
    second = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "vibecell.note_append", "arguments": {"markdown": "Second note."}},
    })
    import json
    out = json.loads(second.json()["result"]["content"][0]["text"])
    assert "First note." in out["notes"]
    assert "Second note." in out["notes"]
    assert "---" in out["notes"]  # divider between entries
```

- [ ] **Implementation:**

```python
from datetime import datetime, timezone
from app.services.notes import NotesService

async def handle_note_append(args, ctx):
    slug = await ProjectService(ctx.db).get_active_slug(ctx.workspace_id, ctx.user_id)
    if slug is None:
        raise RuntimeError("No active project")
    svc = NotesService(ctx.db)
    existing = await svc.get(ctx.workspace_id, slug)
    stamp = datetime.now(timezone.utc).isoformat()
    appended = f"{stamp}\n{args.markdown}" if not existing.strip() else f"{existing}\n\n---\n\n{stamp}\n{args.markdown}"
    await svc.put(ctx.workspace_id, slug, appended)
    return json.dumps({"notes": appended})
```

- [ ] **Commit.**

### 2.6.g — `vibecell.ship`

- [ ] **Test:**

```python
# backend/tests/test_mcp_tools/test_ship.py
async def test_ship_creates_row_and_lifecycle_event(mcp_client, user_workspace_with_active_project, async_session) -> None:
    import json
    from sqlalchemy import select
    from app.models.lifecycle_events import LifecycleEvent  # existing from Spec 2
    resp = await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.ship", "arguments": {
            "version": "v0.1.0",
            "summary": "First ship",
            "changelog_md": "## v0.1.0\n\n- initial",
        }},
    })
    data = json.loads(resp.json()["result"]["content"][0]["text"])
    assert data["id"]
    evs = (await async_session.execute(
        select(LifecycleEvent).where(LifecycleEvent.kind == "shipped")
    )).scalars().all()
    assert any(e.detail.get("version") == "v0.1.0" for e in evs)
```

- [ ] **Implementation:**

```python
from datetime import datetime, timezone
from app.services.ships import ShipService

async def handle_ship(args, ctx):
    slug = await ProjectService(ctx.db).get_active_slug(ctx.workspace_id, ctx.user_id)
    if slug is None:
        raise RuntimeError("No active project")
    svc = ShipService(ctx.db)
    row = await svc.create(
        workspace_id=ctx.workspace_id, project_slug=slug,
        shipped_at=datetime.now(timezone.utc),
        version=args.version, summary=args.summary, changelog_md=args.changelog_md,
    )
    return json.dumps({"id": row.id, "version": row.version})
```

- [ ] **Commit.**

### 2.6.h — `vibecell.status`

- [ ] **Test:**

```python
# backend/tests/test_mcp_tools/test_status.py
async def test_status_updates_project(mcp_client, user_workspace_with_active_project, async_session) -> None:
    import json
    from app.services.projects import ProjectService
    await mcp_client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "vibecell.status", "arguments": {"status": "paused"}},
    })
    svc = ProjectService(async_session)
    agg = await svc.get_aggregate(user_workspace_with_active_project["workspace"].id, "vibecell")
    assert agg["status"] == "paused"
```

- [ ] **Implementation:**

```python
async def handle_status(args, ctx):
    svc = ProjectService(ctx.db)
    slug = await svc.get_active_slug(ctx.workspace_id, ctx.user_id)
    if slug is None:
        raise RuntimeError("No active project")
    updated = await svc.patch(ctx.workspace_id, slug, {"status": args.status})
    return json.dumps({"slug": slug, "status": updated["status"]})
```

- [ ] **Commit.**

---

## Task 2.7 — Fixture additions

**Files:**
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Add fixtures used by handler tests**

```python
# backend/tests/conftest.py (additions)

@pytest_asyncio.fixture
async def user_workspace_with_active_project(async_session, user_workspace):
    """Seed a 'vibecell' project marked as active."""
    from app.services.projects import ProjectService
    svc = ProjectService(async_session)
    p = await svc.create(
        workspace_id=user_workspace.id, slug="vibecell", name="Vibecell",
        pitch="Test project", status="live", user_id=user_workspace.owner_id,
    )
    await svc.set_active(user_workspace.id, user_workspace.owner_id, "vibecell")
    yield {"workspace": user_workspace, "project": p}


@pytest_asyncio.fixture
async def user_workspace_with_two_projects(async_session, user_workspace_with_active_project):
    from app.services.projects import ProjectService
    svc = ProjectService(async_session)
    await svc.create(
        workspace_id=user_workspace_with_active_project["workspace"].id,
        slug="other", name="Other", pitch="", status="building",
        user_id=user_workspace_with_active_project["workspace"].owner_id,
    )
    yield user_workspace_with_active_project


@pytest_asyncio.fixture
async def mcp_client_no_active_project(client, registered_oauth_client, user_workspace):
    """Issue a token for a workspace with no active project selected."""
    # (reuse issued_token_pair pattern but do NOT seed active project)
    ...
```

- [ ] **Step 2: Run the full test suite**

```bash
cd backend && uv run pytest tests/test_mcp_tools/ -v
```
Expected: All 17 handler-test files PASS (each tool tested).

- [ ] **Step 3: Commit fixtures**

```bash
git add backend/tests/conftest.py
git commit -m "test(mcp): fixtures for active-project / multi-project scenarios"
```

---

## Task 2.8 — End-of-Phase integration test

**Files:**
- Create: `backend/tests/integration/test_full_oauth_mcp_flow.py`

- [ ] **Step 1: Write E2E test**

```python
# backend/tests/integration/test_full_oauth_mcp_flow.py
"""register → authorize → token → mcp initialize → tools/list → tools/call."""
import base64
import hashlib


async def test_end_to_end_oauth_and_mcp(client, authed_client, user_workspace) -> None:
    reg = (await client.post("/oauth/register", json={
        "client_name": "e2e", "redirect_uris": ["http://127.0.0.1:1/cb"],
    })).json()
    cid = reg["client_id"]

    verifier = "v" + "a" * 42
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri=http://127.0.0.1:1/cb"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=e&scope=vibecell:tools",
    )
    g = await authed_client.post("/oauth/grant", json={"state": "e", "workspace_id": user_workspace.id}, follow_redirects=False)
    code = g.headers["location"].split("code=")[1].split("&")[0]

    tok = (await client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": "http://127.0.0.1:1/cb",
        "client_id": cid, "code_verifier": verifier,
    })).json()

    client.headers["Authorization"] = f"Bearer {tok['access_token']}"

    init = (await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
    })).json()
    assert init["result"]["serverInfo"]["name"] == "vibecell"

    tl = (await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    })).json()
    assert len(tl["result"]["tools"]) == 17

    ping = (await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "vibecell.ping", "arguments": {}},
    })).json()
    assert "content" in ping["result"]
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/integration/test_full_oauth_mcp_flow.py -v`
Expected: PASS.

- [ ] **Step 3: Phase-close commit**

```bash
git add backend/tests/integration/test_full_oauth_mcp_flow.py
git commit -m "test(mcp): E2E — register → authorize → token → mcp initialize/list/call"
```

---

## End of Phase 2 — Checklist

- [ ] `/mcp` responds to `initialize`, `ping`, `tools/list`, `tools/call`
- [ ] 17 tools registered; `vibecell.run` absent
- [ ] Every tool has a live handler wired to backend services (no stubs left)
- [ ] Every tool call writes to `mcp_audit_log`
- [ ] Bearer-JWT middleware enforces auth + scope + JTI blacklist
- [ ] Coverage ≥ 85% on `backend/app/mcp/`
- [ ] Full OAuth+MCP E2E integration test passes
- [ ] `uv run pytest -q` green overall

Proceed to Phase 3.
