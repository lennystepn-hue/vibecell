# Vibecell — Security posture

Last audit: **2026-04-22** (commit to be tagged on push).

## Transport & edge
- **TLS** terminated at Cloudflare edge. HSTS preload (`max-age=63072000; includeSubDomains; preload`) emitted by origin nginx as failover.
- **HTTP security headers** on every response (nginx `add_header … always`):
  - `Strict-Transport-Security` (2 years)
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()`
  - `Content-Security-Policy`:
    ```
    default-src 'self';
    script-src 'self';
    style-src 'self' 'unsafe-inline';
    img-src 'self' data: https:;
    font-src 'self' data:;
    connect-src 'self';
    frame-ancestors 'none';
    base-uri 'self';
    form-action 'self';
    object-src 'none';
    ```
- **SSE endpoint** has its own nginx location with `proxy_buffering off` and 24h read-timeout. Heartbeats every 20s keep idle streams alive.

## Auth & sessions
- Magic-link sign-in only (no passwords stored). Link TTL 15 min, single-use.
- Session cookie: `hangar_session`, flags `HttpOnly=true`, `Secure=true` (prod), `SameSite=Lax`, `Path=/`, `Domain=vibecell.dev`. Max-age = 30 days.
- MCP endpoint (Streamable HTTP) uses **OAuth 2.1** (RFC 6749 + PKCE S256, RS256 JWTs, RFC 9068 `typ=at+jwt`, RFC 7591 Dynamic Client Registration, RFC 9728 Protected Resource Metadata). JWKS published at `/.well-known/jwks.json`.
- WebAuthn (passkey) optional second factor; lib: `py_webauthn`.

## Application-level
- **SQL injection** — 100 % SQLAlchemy ORM / parameterised `text()` with named binds. No f-strings or `%s` building raw queries. Audited via grep `execute\(f"|\.format\(.*SELECT|\.raw`.
- **Stored XSS** — search results (Postgres `ts_headline`) previously rendered via `v-html`. The default `<b>/<b>` highlight markers did not escape input text, so session/decision/idea bodies containing HTML would inject. **Fix (commit to land):** `ts_headline` now uses custom sentinels `⟦HL⟧` / `⟦/HL⟧`, and the frontend HTML-escapes the whole snippet before re-wrapping matches in `<mark>`. The ONLY remaining `v-html` call is this sanitised render path.
- **CSRF** — state-changing endpoints require session cookie (SameSite=Lax blocks cross-site POSTs from browsers). OAuth endpoints use PKCE. No `<form>` cross-origin targets exist.
- **Workspace isolation** — every `require_project` / `require_workspace_member` dep filters by `workspace_id` against the active session's workspace. Verified each handler chains one of these dependencies.
- **Secrets at rest** — `inline_encrypted` values go through workspace-scoped DEK (AES-256-GCM) wrapped by the platform master key. `op://` / `bw://` / `ssh-agent://` references store path only; plaintext never touches the server. Secret *reads* log `secret.used` events (for audit).
- **Rate limiting**
  - MCP tool calls: Prometheus-gated plus implicit through HTTP rate limits.
  - **AI endpoints (new)**: Redis sliding-window, 20 calls/hour per (user, project). Returns 429 + `Retry-After` header. Fails-open on Redis outage so a Redis hiccup never blocks the user entirely.
  - Magic-link request: limited per email/IP via the Redis window (existing `rate_limit.py`).

## Data at rest
- Postgres 16 in docker-compose, `pg-data` volume on Hetzner VPS.
- **Daily backup**: `systemd` timer at 03:00 UTC runs `ops/backup.sh` — gzipped `pg_dump` into `/srv/hangar/backups/{daily,weekly,monthly}`. Retention: 7d / 4w / 3m.
- `project_screenshots` stored as `.webp` on a named docker volume (`screenshots`).

## Dependencies
- Backend: FastAPI 0.115+, SQLAlchemy 2.0.36+, asyncpg 0.30+, Pydantic 2.9+, cryptography 44+, pyjwt 2.12+, anthropic 0.96+, webauthn 2.7+.
- Frontend: Vue 3, TypeScript, Tailwind, Vite.
- **Pending**: automated `pip-audit` / `npm audit` in CI.

## Known gaps (tracked)
- **No Sentry** yet. `HANGAR_SENTRY_DSN` field reserved; Sentry SDK not wired.
- **Key rotation** scripted for JWT private key and WorkspaceKey DEKs — no documented runbook yet.
- **Per-connection egress throttling** on MCP not implemented (we rely on client sanity + platform metrics).
- **`X-Frame-Options` duplicated**: Cloudflare emits `SAMEORIGIN` on top of our `DENY`. Browsers honour the first (DENY) — acceptable for now.

## Reporting
- Security issues: email `security@vibecell.dev` (forwarded to maintainer). Please DO NOT open a public issue for undisclosed vulns.
