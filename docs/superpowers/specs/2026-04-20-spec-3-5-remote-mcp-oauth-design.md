# Spec 3.5 — Remote MCP Server on vibecell.dev with OAuth 2.1

**Status:** Design approved (2026-04-20). Implementation pending.
**Depends on:** Spec 1 (auth, workspaces, projects), Spec 2 (sessions, decisions, ideas, notes, ships), Spec 3 (CLI + MCP tool semantics).
**Enables:** Zero-install onboarding for Claude Desktop, Cursor, Zed, Windsurf, and any future MCP client.

---

## Goal

Users click a button on vibecell.dev (or enter `https://vibecell.dev` as a remote MCP server in their client), consent in a branded OAuth screen, and their Claude Desktop / Cursor / Zed instance has the full vibecell tool set available with zero local install. The existing Rust CLI daemon stays — it is the only way to use `vibecell.run` (local shell command execution with secrets) and the only option for offline/air-gapped work.

---

## Non-Goals

- Replacing the local `hangar daemon`. It keeps shipping and remains the recommended install for power users.
- Supporting `vibecell.run` over remote MCP. Local command execution + secret resolution needs the user's machine.
- Team-level OAuth clients (org-wide installs). v1 scopes each token to a single user in a single workspace. Team/org installs are deferred.
- Fine-grained scopes (`vibecell:read` vs `vibecell:write`). v1 has one scope, `vibecell:tools`, covering all 17 remote tools. Granularity can be added without breaking changes.

---

## Architecture

### Backend modules

```
backend/app/
├── oauth/
│   ├── server.py       # Authorization Server (authorize/token/revoke/register)
│   ├── discovery.py    # /.well-known/oauth-authorization-server + /.well-known/oauth-protected-resource
│   ├── models.py       # OAuthClient, AuthCode, AccessToken, RefreshToken tables
│   └── consent.py      # Consent-state + grant management
├── mcp/
│   ├── server.py       # Streamable HTTP MCP endpoint
│   ├── tools.py        # Tool dispatch — mirrors cli/src/daemon/tools.rs logic
│   └── session.py      # Per-connection session state
└── api/v1/connections.py  # List/revoke connected clients (user settings API)
```

### Frontend pages

```
frontend/src/pages/
├── OAuthConsent.vue     # /oauth/authorize?... — renders the consent screen
└── Connections.vue      # /settings/connections — list + revoke connected clients
```

### New database tables (Alembic migration 0005)

- `oauth_clients` — DCR-registered clients. Columns: id, client_id, client_name, redirect_uris (array), scope, created_at, last_used_at, revoked_at, registered_by_user_id (nullable — null means registered via unauth'd DCR, common for Claude Desktop).
- `oauth_auth_codes` — short-lived authorization codes. Columns: code, client_id, user_id, workspace_id, code_challenge, redirect_uri, scope, expires_at (now + 60s), consumed_at.
- `oauth_access_tokens` — issued JWTs tracked by `jti` for revocation. Columns: jti, client_id, user_id, workspace_id, scope, issued_at, expires_at, revoked_at.
- `oauth_refresh_tokens` — opaque refresh tokens. Columns: token_hash (sha256), client_id, user_id, workspace_id, scope, issued_at, expires_at (now + 30d), consumed_at (single-use rotation), revoked_at.
- `mcp_audit_log` — tool-call log for the connections UI counter. Columns: id, client_id, workspace_id, user_id, tool_name, called_at, duration_ms, status. Retention: 30 days (daily cron prune).

All tables have `workspace_id` where applicable so revocation can cascade on workspace deletion.

### Data flow — connect

```
1. Claude Desktop → GET  /.well-known/oauth-authorization-server     (discovery)
2.                → POST /oauth/register                              (dynamic client registration)
3.                → Browser opens → GET /oauth/authorize?...          (authorize request)
4.   vibecell.dev → renders /oauth/consent (user signed in + workspace picker)
5.   user clicks  → POST /oauth/grant { workspace_id, grant }
6.                → redirect to client's redirect_uri?code=...&state=...
7. Claude Desktop → POST /oauth/token { code, code_verifier }         (PKCE exchange)
8.                → access_token (JWT, 1h) + refresh_token (opaque, 30d)
9.                → POST /mcp { jsonrpc, method: "initialize", ... }
10.               → POST /mcp { jsonrpc, method: "tools/list" }       (17 tools)
11. connected.
```

### Data flow — tool call

```
Claude Desktop → POST /mcp                   (Authorization: Bearer <jwt>)
                 { jsonrpc: "2.0", id: N, method: "tools/call",
                   params: { name: "vibecell.idea", arguments: { body: "..." } } }

Backend:
  → auth_middleware: validate JWT, check jti not revoked, extract workspace_id
  → tools.py: dispatch "vibecell.idea" → IdeaService(db).create(workspace_id, body)
  → mcp_audit_log insert (fire-and-forget)
  → respond { jsonrpc: "2.0", id: N, result: { content: [{ type: "text", text: json }] } }
```

Handlers call backend services directly — no HTTP self-calls to `/api/v1/*`. Tool registry is a shared module so docs generation, tests, and the live server all use the same names/schemas.

---

## OAuth 2.1 Details

### Discovery — `/.well-known/oauth-authorization-server` (RFC 8414)

```json
{
  "issuer": "https://vibecell.dev",
  "authorization_endpoint": "https://vibecell.dev/oauth/authorize",
  "token_endpoint": "https://vibecell.dev/oauth/token",
  "revocation_endpoint": "https://vibecell.dev/oauth/revoke",
  "registration_endpoint": "https://vibecell.dev/oauth/register",
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code", "refresh_token"],
  "code_challenge_methods_supported": ["S256"],
  "token_endpoint_auth_methods_supported": ["none", "client_secret_basic"],
  "scopes_supported": ["vibecell:tools"]
}
```

### Discovery — `/.well-known/oauth-protected-resource` (RFC 9728)

```json
{
  "resource": "https://vibecell.dev/mcp",
  "authorization_servers": ["https://vibecell.dev"],
  "scopes_supported": ["vibecell:tools"],
  "bearer_methods_supported": ["header"]
}
```

### Dynamic Client Registration (RFC 7591)

`POST /oauth/register` with body `{ client_name, redirect_uris, scope }`.
Response: `{ client_id, client_id_issued_at, redirect_uris, scope, token_endpoint_auth_method: "none" }`.

- Public clients only. No `client_secret`. MCP Desktop clients are non-confidential per spec.
- Rate-limit: 10/min per IP.
- Orphan cleanup: clients registered via unauth'd DCR that never complete an authorize flow within 24h are auto-deleted by a daily cron.
- Per-user authorized-client cap: 50. Counted against clients that have successfully completed an authorize flow for a given user (at which point `oauth_clients.registered_by_user_id` is backfilled). Oldest-unused auto-revoked when cap hit.
- `redirect_uri` must be HTTPS OR a loopback (`http://127.0.0.1:*` or `http://localhost:*`) — needed for Claude Desktop which uses a loopback callback.

### Authorize

`GET /oauth/authorize?response_type=code&client_id=...&redirect_uri=...&code_challenge=...&code_challenge_method=S256&state=...&scope=vibecell:tools`

- If user not signed in → redirect to `/login?next=...` (magic-link flow), return to authorize after success.
- If signed in → render `/oauth/consent` (Vue page) with:
  - Client name, registration time, redirect_uri for transparency.
  - Workspace picker (default: user's `active_workspace_id`).
  - Permission list (hardcoded for v1, documented below).
  - Allow/Deny buttons.
- Allow → `POST /oauth/grant { workspace_id }` → server stores auth_code (60s TTL, single-use, bound to client_id + workspace_id + code_challenge) → redirect to `redirect_uri?code=...&state=...`.
- Deny → redirect to `redirect_uri?error=access_denied&state=...`.

### Token

`POST /oauth/token` (application/x-www-form-urlencoded):

- `grant_type=authorization_code&code=...&code_verifier=...&redirect_uri=...&client_id=...`
  - Validate PKCE (S256 only — plain rejected).
  - Validate code (exists, not consumed, not expired, matches client_id + redirect_uri).
  - Mark consumed. Issue access_token (JWT, 1h) + refresh_token (opaque, 30d).
- `grant_type=refresh_token&refresh_token=...&client_id=...`
  - Validate refresh_token (exists, not consumed, not revoked, not expired).
  - Mark consumed. Rotate: issue new access_token + new refresh_token.

Response:
```json
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "rt_...",
  "scope": "vibecell:tools"
}
```

### Revoke

`POST /oauth/revoke` (application/x-www-form-urlencoded) with `token=...&token_type_hint=access_token|refresh_token`.
Returns 200 regardless of validity (RFC 7009).

Revocation cascades: revoking an access_token blacklists its `jti` in Redis (TTL = token's remaining lifetime). Revoking a refresh_token invalidates it AND all access_tokens issued from its chain (tracked via `refresh_token_family_id` in `oauth_access_tokens.issued_from_refresh`).

### Access token (JWT)

Claims:
```json
{
  "iss": "https://vibecell.dev",
  "sub": "<user_id>",
  "aud": "https://vibecell.dev/mcp",
  "client_id": "<client_id>",
  "workspace_id": "<workspace_id>",
  "scope": "vibecell:tools",
  "exp": <unix>,
  "iat": <unix>,
  "jti": "<ulid>"
}
```

Signing: HMAC-SHA256 with a dedicated secret (`OAUTH_JWT_SECRET` env, distinct from magic-link signing). Future upgrade path: RS256 with published JWKS at `/.well-known/jwks.json` — not needed v1.

### Security invariants

- PKCE S256 REQUIRED. `plain` rejected. No PKCE → `invalid_request`.
- `state` parameter REQUIRED on authorize. CSRF protection.
- `redirect_uri` exact-match on both authorize and token (no `startsWith`).
- Rate-limits: `/oauth/register` 10/min/IP, `/oauth/token` 20/min/client_id, `/oauth/authorize` 30/min/IP (no user at authorize-time if not yet signed in).
- CORS on `/mcp` endpoint: no Origin header expected from Desktop; explicit reject any Origin except localhost (development).

---

## MCP Endpoint

### Transport

MCP Spec 2025-06 "Streamable HTTP". Single endpoint: `POST /mcp`. Content-Type `application/json`. Streaming responses via `text/event-stream` are spec-supported but unused in v1 (all our tools return fast).

`GET /mcp` for server-initiated notifications is not implemented in v1 (no push events needed).

### Handler

```python
@router.post("/mcp")
async def mcp_handler(req: Request, ctx: MCPContext = Depends(auth_middleware)):
    body = await req.json()
    method = body.get("method")
    req_id = body.get("id")

    try:
        match method:
            case "initialize":
                result = handshake(body["params"], ctx)
            case "tools/list":
                result = list_tools(ctx)
            case "tools/call":
                result = await call_tool(body["params"], ctx)
            case "ping":
                result = {}
            case _:
                return jsonrpc_error(req_id, -32601, "Method not found")
    except ToolError as e:
        return jsonrpc_tool_error(req_id, e)
    except Exception:
        capture_exception()
        return jsonrpc_error(req_id, -32603, "Internal error")

    return {"jsonrpc": "2.0", "id": req_id, "result": result}
```

`initialize` response:
```json
{
  "protocolVersion": "2025-06-18",
  "capabilities": { "tools": {} },
  "serverInfo": { "name": "vibecell", "version": "X.Y" }
}
```

### Tool registry

```python
# backend/app/mcp/tools.py
from pydantic import BaseModel

class PingArgs(BaseModel): pass

class IdeaArgs(BaseModel):
    body: str
    project: str | None = None

TOOLS = [
    Tool("vibecell.ping",            PingArgs,           handle_ping),
    Tool("vibecell.active",          NoArgs,             handle_active),
    Tool("vibecell.list",            ListArgs,           handle_list),
    Tool("vibecell.get",             GetArgs,            handle_get),
    Tool("vibecell.brief",           BriefArgs,          handle_brief),
    Tool("vibecell.search",          SearchArgs,         handle_search),
    Tool("vibecell.recent_projects", RecentArgs,         handle_recent),
    Tool("vibecell.switch",          SwitchArgs,         handle_switch),
    Tool("vibecell.log_session",     LogSessionArgs,     handle_log_session),
    Tool("vibecell.update_context",  UpdateContextArgs,  handle_update_context),
    Tool("vibecell.decision",        DecisionArgs,       handle_decision),
    Tool("vibecell.idea",            IdeaArgs,           handle_idea),
    Tool("vibecell.note_append",     NoteAppendArgs,     handle_note_append),
    Tool("vibecell.ship",            ShipArgs,           handle_ship),
    Tool("vibecell.status",          StatusArgs,         handle_status),
    Tool("vibecell.claude_md",       ClaudeMdArgs,       handle_claude_md),
    Tool("vibecell.handover",        HandoverArgs,       handle_handover),
]
# NOTE: vibecell.run is intentionally absent. Local-CLI only.

TOOLS_BY_NAME = {t.name: t for t in TOOLS}
```

### Auth middleware

```python
async def auth_middleware(req: Request, db: Session = Depends(get_db)) -> MCPContext:
    header = req.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, headers=resource_metadata_header())
    token = header[7:]
    try:
        claims = jwt.decode(token, OAUTH_JWT_SECRET, algorithms=["HS256"], audience="https://vibecell.dev/mcp")
    except jwt.InvalidTokenError:
        raise HTTPException(401, headers=resource_metadata_header())
    if await is_jti_revoked(claims["jti"]):
        raise HTTPException(401, headers=resource_metadata_header())
    if "vibecell:tools" not in claims["scope"].split():
        raise HTTPException(403, detail="insufficient_scope")
    return MCPContext(
        db=db,
        user_id=claims["sub"],
        workspace_id=claims["workspace_id"],
        client_id=claims["client_id"],
        jti=claims["jti"],
    )

def resource_metadata_header() -> dict:
    return {"WWW-Authenticate": 'Bearer resource_metadata="https://vibecell.dev/.well-known/oauth-protected-resource"'}
```

### Workspace scoping

Every JWT is bound to one `workspace_id`. All tool handlers filter by `ctx.workspace_id`. `vibecell.switch(slug)` switches the user's active *project* within the workspace — it cannot change workspaces. A user who works across multiple workspaces connects separately per workspace (separate OAuth flows, separate Desktop entries).

### Tool response shape

MCP spec: `tools/call` returns `{ content: [{ type: "text", text: "..." }], isError?: bool }`.

Successful responses: `content[0].text` is JSON-stringified data, matching the existing Rust daemon output. Keeps Claude's prompt-side handling identical whether it's talking to remote or local.

Error responses: `{ content: [{ type: "text", text: "Error message" }], isError: true }` — surface-level tool errors (e.g. "project not found"). System errors (DB down) still return JSON-RPC error with code -32603.

---

## Consent Screen UI

`/oauth/consent` renders inside Vue app with Cockpit theme:

```
┌─────────────────────────────────────────────────────────────────┐
│  ◈ vibecell                signed in as lennystepn@gmail.com     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Claude Desktop wants to connect                                │
│                                                                 │
│  ┌─────────────────────────────────────┐                        │
│  │ 🔷 Claude Desktop                   │                        │
│  │    Client ID: dyn_01KPX...          │                        │
│  │    Registered just now              │                        │
│  │    Redirect: http://127.0.0.1:12345 │                        │
│  └─────────────────────────────────────┘                        │
│                                                                 │
│  It will be able to:                                            │
│  ✓ Read your projects, sessions, decisions, ideas, notes        │
│  ✓ Log sessions, create decisions, capture ideas                │
│  ✓ Append to project notes, record ships                        │
│  ✓ Update project context (focus, next step, open questions)    │
│  ✗ Cannot run local commands (CLI-only)                         │
│  ✗ Cannot access other workspaces                               │
│                                                                 │
│  Connect to workspace:                                          │
│  ┌─────────────────────────────────────┐                        │
│  │ ▼ lennystepn (personal)             │                        │
│  └─────────────────────────────────────┘                        │
│                                                                 │
│  [  Deny  ]                       [  Allow & Connect  ]         │
│                                                                 │
│  You can revoke this connection anytime at                      │
│  vibecell.dev/settings/connections                              │
└─────────────────────────────────────────────────────────────────┘
```

### Card content

- **Icon** — whitelist (Claude, Cursor, Zed, Windsurf) plus a generic MCP icon. Mapping via `client_name` substring match; fallback generic.
- **Client name** — from DCR. If missing or "unnamed", fallback to "Unnamed MCP Client" with warning tint.
- **Redirect URI** — displayed for user verification. Localhost URIs show in muted text; non-localhost HTTPS in normal text.
- **Registered just now** vs **Last connected X ago** — if same client_id connects again, show "Last connected 3 days ago".

### Permissions list

Hardcoded in v1 (all or nothing). The negative bullets are important for trust: users see what the remote client cannot do.

### Workspace picker

`select` showing all workspaces where user is `owner`, `admin`, or `member`. Default: user's `active_workspace_id`. Disabled if user has only one workspace.

### Buttons

- **Deny** → `POST /oauth/deny { state }` → redirect `redirect_uri?error=access_denied&state=...`.
- **Allow & Connect** → `POST /oauth/grant { workspace_id, state }` → server issues auth_code → redirect `redirect_uri?code=...&state=...`.

---

## Connect Button on Dashboard

`/` (Dashboard) and `/settings/connections` both show a "Connect to Claude Desktop" CTA.

Button click opens modal:

```
┌────────────────────────────────────────────────────────────┐
│  Connect Claude Desktop                                    │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  [ Try one-click (Claude Desktop 0.X+) ]                   │
│                                                            │
│  ─── or copy the URL manually ───                          │
│                                                            │
│  1. Open Claude Desktop → Settings → Connectors            │
│  2. Click "Add Remote Server"                              │
│  3. Paste:                                                 │
│                                                            │
│     [ https://vibecell.dev              ] [ Copy ]         │
│                                                            │
│  4. Follow the sign-in prompt in your browser              │
│                                                            │
│  Works with: Claude Desktop, Cursor, Zed, Windsurf         │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

- **One-click button** — opens `claude://add-connector?url=https%3A%2F%2Fvibecell.dev`. If the deep-link is handled (Claude Desktop 0.X+ with MCP connector support), Desktop intercepts and prompts. If not handled, nothing visible happens — user falls back to manual URL.
- **Copy button** — clipboard-copies `https://vibecell.dev`.
- **Tool-specific tabs** (nice-to-have, v1.1): add dropdown for Cursor/Zed/Windsurf with their respective deep-link schemes.

---

## Connections Settings Page

`/settings/connections` — unified view of everything that has workspace access:

```
┌──────────────────────────────────────────────────────────────────┐
│  Connections                                                     │
│  Apps and clients with access to your workspaces                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 🔷 Claude Desktop                           [ Revoke ]     │  │
│  │    Workspace: lennystepn · Connected 2h ago                │  │
│  │    Last used: 3m ago · 47 tool calls today                 │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 📐 Cursor                                   [ Revoke ]     │  │
│  │    Workspace: lennystepn · Connected yesterday             │  │
│  │    Last used: 18h ago · 12 tool calls                      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 🪄 Device: ender-win (hangar CLI)           [ Unpair ]     │  │
│  │    Paired 2 days ago · last sync 3m ago                    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  + Connect another app                                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Unified data source

`GET /api/v1/connections` returns merged list:
- OAuth clients (from `oauth_clients` where `revoked_at IS NULL` + joined with user scope)
- CLI devices (from existing `cli_devices` table)

Each entry: `id, type ("oauth" | "cli"), name, icon, workspace_name, connected_at, last_used_at, tool_calls_today, tool_calls_total, revoke_url`.

Sort: `last_used_at DESC`.

### Revoke action

- `DELETE /api/v1/connections/{id}` — polymorphic. For OAuth: revoke all active tokens + set `oauth_clients.revoked_at`. For CLI: delete keychain server-side entry, remove `cli_devices` row.
- Confirmation modal: "This will disconnect X immediately. You can reconnect anytime."
- Immediate effect: JTI blacklist populated, next request returns 401.

### Activity counter

`mcp_audit_log` aggregated per-client. Today-count: `WHERE client_id = X AND called_at > today_start`. Total: `WHERE client_id = X`. Indexed `(client_id, called_at DESC)`.

---

## Error Handling

### Auth errors at `/mcp`

| Condition | HTTP | Body | WWW-Authenticate |
|-----------|------|------|-----------------|
| Missing Bearer | 401 | — | `Bearer resource_metadata=...` |
| Invalid/expired JWT | 401 | — | `Bearer error="invalid_token"` |
| Revoked JTI | 401 | — | `Bearer error="invalid_token"` |
| Wrong scope | 403 | `{"error": "insufficient_scope"}` | `Bearer error="insufficient_scope"` |

### Tool-level errors

- **Unknown tool** → JSON-RPC `-32602` "Unknown tool: X".
- **Invalid args** (pydantic validation fails) → JSON-RPC `-32602` with validation message.
- **Backend service error** (DB down, upstream fail) → JSON-RPC `-32603` "Internal error" + Sentry capture.
- **Tool-specific errors** (e.g. `vibecell.switch` with non-existent slug) → successful JSON-RPC response with `{ result: { content: [...], isError: true } }` + user-friendly message. Not a system-level error.

### Edge cases

1. **User logs out between consent and token exchange** — `/oauth/token` validates user still exists and has workspace access. Fail: `invalid_grant`. Claude Desktop restarts OAuth flow.
2. **Workspace deleted while client connected** — cascading DB trigger revokes all tokens scoped to that workspace. Next tool call: 401.
3. **DCR spam** — rate-limit 10/min/IP. If a user accumulates > 50 registered clients, oldest-unused is auto-revoked on next registration.
4. **Concurrent refresh_token use** — tokens are single-use. First caller gets new token pair, second caller gets `invalid_grant` → Desktop restarts OAuth.
5. **vibecell.dev offline during active session** — Desktop sees transport error, exponential-backoff retry. On token expiry during outage, next successful request triggers re-OAuth.

### Observability

- Prometheus metrics:
  - `oauth_tokens_issued_total{client_name}` counter
  - `oauth_authorize_redirects_total{outcome}` counter (`granted|denied|error`)
  - `mcp_tool_calls_total{tool_name, status}` counter
  - `mcp_tool_errors_total{tool_name, error_type}` counter
  - `mcp_auth_failures_total{reason}` counter
  - `mcp_active_connections` gauge
- Structured logs: every MCP call (debug level), every auth failure (info level), every OAuth error (warn level).
- Sentry: wrap all tool handlers, send exceptions with tool_name + client_id tags (not arguments).

---

## Testing

### New test modules

```
backend/tests/
├── test_oauth_discovery.py          # both .well-known endpoints return spec-compliant JSON
├── test_oauth_register.py           # DCR success, redirect_uri validation, rate-limit, per-user cap
├── test_oauth_authorize.py          # sign-in redirect, consent render, workspace picker, allow/deny paths
├── test_oauth_token.py              # code→token, PKCE S256 enforcement, refresh rotation, single-use refresh, expired/revoked rejection
├── test_oauth_revoke.py             # revoke access + refresh, cascade, JTI blacklist
├── test_mcp_handler.py              # JSON-RPC dispatch, initialize/list/call, unknown method
├── test_mcp_auth_middleware.py      # bearer required, JWT validation, scope check, revoked JTI
├── test_mcp_tools/                  # one file per tool, mirrors cli test style
│   ├── test_ping.py
│   ├── test_active.py
│   ├── ... (17 files)
│   └── test_run_absent.py           # verify vibecell.run is NOT in tools/list
├── test_connections_api.py          # list merges oauth+cli, revoke polymorphic
├── test_mcp_audit_log.py            # audit entries written on tool call, retention cron
└── integration/
    └── test_full_oauth_mcp_flow.py  # register → authorize → token → mcp-call → revoke
```

Coverage target: ≥ 85% for `backend/app/oauth/` and `backend/app/mcp/`.

### Frontend tests

Playwright E2E, 2 scenarios:
1. **allow path** — sign in, visit authorize URL with mock client params, pick workspace, click Allow, verify redirect with code.
2. **deny path** — same setup, click Deny, verify redirect with `access_denied`.

### Manual verification

1. `gh pr` with the implementation triggers CI → all green.
2. Against staging, run full flow with `curl` following OAuth 2.1 spec (scripted).
3. Install Claude Desktop on macOS + Windows, add `https://vibecell-staging.dev` (staging domain) as remote server, verify consent screen renders and tools work.
4. Revoke via Connections page, verify next tool call returns 401 and Desktop re-prompts OAuth.

---

## Rollout (Phases of this spec)

1. **Phase 1** — database migrations (0005) + OAuth server (no MCP yet). Deploy to staging. Verify discovery + DCR + authorize + token work via curl.
2. **Phase 2** — MCP endpoint + tool dispatch. Wire tools to backend services. All 17 tools tested with fake JWT.
3. **Phase 3** — Frontend consent screen + connections page. Deploy to staging.
4. **Phase 4** — Connect button on dashboard, deep-link, docs update, Prometheus/Grafana panel.
5. **Phase 5** — Production rollout. Announce. Monitor metrics for 2 weeks before marking stable.

---

## Out of Scope (Explicitly)

- Team / org-wide OAuth clients
- Fine-grained scopes (read vs write)
- `vibecell.run` over remote
- Remote CLI pairing via OAuth (CLI keeps its existing device-code flow)
- Streaming responses from tools (MCP SSE support)
- Push notifications from server to client (GET /mcp for server-initiated events)
- JWKS publication (public key discovery) — HS256 v1 is fine, RS256 + JWKS is a future upgrade

---

## Open Questions

None at design time. All decisions resolved:

- Auth model: full OAuth 2.1 (spec-compliant) ✓
- Consent UX: workspace-picker with permissions list ✓
- Tool scope: all 17 tools in v1, no read-only phase ✓
- Architecture: monolithic (FastAPI-hosted, not separate service) ✓
