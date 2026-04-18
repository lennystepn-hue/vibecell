# Spec 1 — Foundation + Projects & Dashboard

**Status:** approved (2026-04-18)
**Scope:** The first of 5 specs that together implement HANGAR.md in full.
**Parent spec:** `HANGAR.md` (root).
**Next spec:** Spec 2 — Ship Loop.

---

## 1. Overview & Scope

### What this spec delivers

A running, production-deployed web application at `hangar.dev` where the owner can:

1. Sign in via magic link
2. Create and manage a workspace
3. Create projects manually or bulk-import from GitHub
4. Edit every field on a project: identity, repos, environments, infra, context (focus / next-step / user-wants / open-questions / known-issues / blocked-by), links, commands, stack, tags
5. Switch between projects via a Cmd+K palette
6. See projects in a dense, keyboard-first dashboard with Cockpit visual language (dark glass + mono accents + phosphor-green signal palette)

Nothing else. No CLI, no MCP, no Claude skill, no ship loop, no AI cost dashboard, no public pages, no billing, no Passkeys, no Stripe, no iOS. Those live in Specs 2–5.

### Explicit deferrals and why

| Deferred | To Spec | Reason |
|---|---|---|
| Ship loop (sessions, decisions, ideas, ships, launches, lifecycle events, notes) | 2 | Consumes Projects foundation; independent feature surface. |
| Search (global FTS over all text) | 2 | Depends on multiple entity types existing first. |
| CLI, MCP server, Claude skill, device pairing | 3 | Standalone subsystem (Rust + MCP). GitHub-in-Spec-1 is enough for dogfood bootstrap while Spec 3 is built. |
| Passkeys | 4 | Magic-link covers Spec 1 auth. Passkeys fold in when public signup opens. |
| Stripe billing | 4 | No paid tier until public launch. |
| Public project pages | 4 | Depends on launch-enabler wave. |
| Legal / compliance (Privacy, Terms, Imprint, DSGVO) | 4 | Required only before public signup opens. |
| Passkey-derived crypto for user secrets | 4 | Spec 1 uses workspace-scoped DEK encrypted with server master key. Migration path to user-derived keys in Spec 4. |
| Portfolio health (Git staleness, SSL, uptime, Dependabot) | 5 | Requires background worker + multiple integrations. |
| AI cost dashboard | 5 | Requires ai-provider connectors. |
| Revenue / P&L (Stripe, Lemon, Paddle, RevenueCat) | 5 | Requires Stripe billing from Spec 4 + connectors. |
| Feedback inbox | 5 | Requires email MX + X integration. |
| Domain inventory (Cloudflare/Namecheap/Porkbun) | 5 | Requires integrations infrastructure. |
| Knowledge vault (prompts, specs, skills, templates, snippets) | 5 | Separate surface; not needed to run Spec 1. |
| iOS companion, browser extension | 5 | Nice-to-have multiplicators. |
| Team / multi-member workspaces | later (post-public-launch) | `workspace_members` schema is in Spec 1 but only 'owner' role supported. |

### Acceptance criteria

Spec 1 is done when all of these are true in production at `hangar.dev`:

1. A new user can request a magic link, click it, and land on an empty dashboard.
2. The empty dashboard prompts them to connect GitHub or create the first project manually.
3. Connecting GitHub via OAuth stores an encrypted token and opens a repo-picker.
4. Bulk-importing N repos creates N projects with auto-filled git_url, default_branch, primary_lang, license, pitch, and a GitHub live-link where applicable.
5. From the project detail view, every field in the scoped tables (see §2) can be edited via the UI, with optimistic updates, audit-logged server-side, and survives page refresh.
6. Cmd+K from anywhere opens the project switcher, fuzzy-matches by slug/name, and navigates to the selected project in < 100 ms perceived latency.
7. Switching a project persists `active_project` for (workspace, user).
8. The entire dashboard runs in Cockpit visual language as specified in §6.
9. CI passes: lint + typecheck + backend tests (against real Postgres) + frontend tests + 3 E2E scenarios.
10. Deploy-to-production happens by push to `main` branch.

---

## 2. Architecture & Deployment Topology

### Monorepo Layout

```
hangar/
├── backend/                    FastAPI + SQLAlchemy + Alembic
│   ├── app/
│   │   ├── api/                v1 routes
│   │   ├── core/               config, db, auth middleware, deps, crypto
│   │   ├── models/             SQLAlchemy ORM
│   │   ├── schemas/            Pydantic v2
│   │   └── services/           auth, projects, integrations/github, audit
│   ├── alembic/
│   ├── tests/                  pytest (integration-first, real DB)
│   └── pyproject.toml
├── frontend/                   Vue 3 + TS + Vite + Pinia
│   ├── src/
│   │   ├── pages/              dashboard, project/:slug, auth/verify, import/github, settings
│   │   ├── components/         ProjectCard, StatusPill, ContextCard, StackChip, ...
│   │   ├── stores/             Pinia: auth, workspace, projects, commandPalette, toast
│   │   ├── composables/
│   │   ├── api/                typed client (generated from openapi.json)
│   │   └── assets/             fonts (Geist, Geist Mono), tokens.css
│   ├── index.html
│   └── package.json
├── ops/
│   ├── docker-compose.yml          prod stack
│   ├── docker-compose.dev.yml      local dev (postgres + redis only)
│   ├── Caddyfile
│   └── deploy.sh
├── docs/
│   └── superpowers/specs/          design docs
└── .github/workflows/ci.yml
```

### Production Topology (Hetzner CX22, ~€4/mo)

```
Caddy (:80, :443, auto-TLS via Let's Encrypt)
  ├─→ hangar.dev                  → frontend static bundle (served by Caddy)
  ├─→ hangar.dev/api/*            → backend:8000 (FastAPI via uvicorn, 2 workers)
  └─→ hangar.dev/healthz          → backend healthcheck

docker-compose services:
  backend   FastAPI + uvicorn (:8000, internal)
  postgres  Postgres 16 (:5432, internal, volume-mounted pg-data)
  redis     Redis 7 (:6379, internal; sessions + rate-limit; AOF enabled)
  caddy     reverse proxy (:80, :443, host-networked)

Volumes:
  pg-data            Postgres data (local SSD)
  caddy-data         TLS certificates
  backups            Nightly pg_dump staging (cron offloads to Hetzner Object Storage, separate region)
```

SSH alias `hangar-prod`. Deploy via GitHub Actions → `ssh hangar-prod "cd /srv/hangar && ./deploy.sh <sha>"`.

### Staging

Same VPS, separate compose project `hangar-staging`, separate DB `hangar_staging`, domain `dev.hangar.dev`. Magic links in staging dev-mode are printed to log instead of emailed.

### Local Dev (macOS / Linux / WSL)

```
docker compose -f ops/docker-compose.dev.yml up -d     # postgres + redis only
uvicorn backend.app.main:app --reload                   # backend :8000
cd frontend && pnpm dev                                 # vite :3000 with /api proxy to :8000
```

Dev uses `backend/.env` (gitignored). A `backend/.env.example` template sits in the repo.

### CI/CD (GitHub Actions)

```yaml
jobs:
  backend:
    services: postgres:16, redis:7
    steps: [ruff check, mypy strict, pytest -v (real DB)]
  frontend:
    steps: [pnpm typecheck, pnpm lint, pnpm test, pnpm build]
  e2e:
    needs: [backend, frontend]
    steps: [docker compose up -d, playwright test]
  deploy:
    if: branch == main && all-green
    steps:
      - buildx → push ghcr.io/lenny/hangar-{backend,frontend}:<sha>
      - ssh hangar-prod "cd /srv/hangar && ./deploy.sh <sha>"
```

`deploy.sh` on server: pulls images, runs `alembic upgrade head` inside backend container, restarts backend + frontend services, health-checks. On health-check failure, rolls back to previous SHA.

---

## 3. Data Model

### Tables in Spec 1 (20 total)

All tables from HANGAR.md §4.1 + §4.2 that are relevant, plus `magic_link_tokens`, `integrations` (subset), and `workspace_keys` (new, see §5 Crypto). ULIDs as Crockford-Base32 text PKs. Timestamps as `TIMESTAMPTZ NOT NULL DEFAULT NOW()`. JSONB defaults to `'[]'::jsonb` for arrays, `'{}'::jsonb` for objects.

**Auth & Workspace**

- `users` — email UNIQUE, name, handle, `passkey_credentials` JSONB (NULL in Spec 1).
- `workspaces` — slug UNIQUE, name, owner_id, plan='free'.
- `workspace_members` — (workspace_id, user_id) → role. Only 'owner' role is used; 'member'/'viewer' land in Spec 4.
- `cli_devices` — schema present, unused in Spec 1 (Spec 3 consumes it).
- `audit_log` — workspace_id, at, actor ('ui:<user_id>' in Spec 1), op, entity, entity_id, diff JSONB.
- `magic_link_tokens` **(new, added for Spec 1)** — id, email, token_hash (sha256 of raw token), created_at, expires_at, consumed_at. Index on `token_hash`. Nightly cleanup of rows where `consumed_at IS NOT NULL OR expires_at < NOW() - 7 days`.

**Projects**

- `projects` — workspace_id, slug UNIQUE-per-workspace, name, emoji, color, pitch, status (`idea | building | live | paused | shipped | archived | dead`), legal_entity_id NULL, is_public=0, created_at, updated_at, archived_at.
- `active_project` — PK (workspace_id), user_id, project_id, set_at. "Last selected" per user/workspace. Full semantics light up in Spec 3.
- `project_repos` — role (`web | api | worker | monorepo | free`), git_url, default_branch='main', local_path, primary_lang, license.
- `project_environments` — kind (`local | preview | staging | prod`), url, env_template_path, db_alias.
- `project_infra` — PK (project_id), server_alias, domain_primary, domains JSONB[], dns_provider, db_host, cdn, object_storage.
- `project_context` — PK (project_id), current_focus, next_step, user_wants, open_questions JSONB[], known_issues JSONB[], blocked_by, updated_at.
- `project_links` — kind, label, url.
- `project_commands` — label, command, run_in (`terminal | background`), confirm_required=1. Execution comes in Spec 3.
- `stack_items` — slug UNIQUE (global catalog), name, kind (`frontend | backend | db | deploy | lib | service | model`), icon_url. **Pre-seeded** via Alembic seed with ~50 entries (Next.js, React, Vue, FastAPI, Rails, Django, Postgres, Supabase, Tailwind, shadcn, Hetzner, Vercel, Fly, Resend, Stripe, Anthropic, OpenAI, Claude, GPT-4, Groq, Replicate, etc.).
- `project_stack` — (project_id, stack_item_id) → role.
- `tags` — workspace_id, name UNIQUE-per-workspace, color.
- `project_tags` — (project_id, tag_id).

**Integrations (subset)**

- `integrations` — workspace_id, project_id NULL, kind, config JSONB, token_ciphertext, connected_at. In Spec 1 only `kind='github'` is handled.
- `workspace_keys` **(new)** — workspace_id PK, dek_ciphertext (AES-256-GCM envelope of a per-workspace DEK, encrypted with `HANGAR_MASTER_KEY`), algorithm='aes-256-gcm-v1', created_at.

### Tables explicitly NOT in Spec 1

All tables in HANGAR.md §4.3 (ship loop), §4.4 (cost & revenue), §4.5 (knowledge vault), §4.6 (inventory, customer loop, health — except the `integrations` row above), §4.7 (legal). `project_secret_refs` from §4.2 is deferred to Spec 3.

### Key schema decisions vs HANGAR.md

1. **IDs.** ULIDs, Crockford-Base32 encoded, 26 chars, TEXT PK. Generated app-side (`python-ulid`). Rationale: HANGAR.md does not spec encoding; Crockford is standard and human-readable.
2. **Soft delete.** `DELETE /projects/:slug` performs a hard `DELETE CASCADE`. Archival is a status change (`status='archived'` + `archived_at=NOW()`). Audit log preserves a 30-day undo window without schema duplication. HANGAR.md §3.14 mentions 30-day audit reversibility — we honour it via audit-log reconstruction, not via soft-delete flags.
3. **RLS (Row-Level Security).** Disabled. Workspace isolation is enforced in application layer (every query filters by `workspace_id` from `request.state.workspace`). Switchable later if we migrate to a platform that rewards RLS.
4. **Search (GIN).** We keep HANGAR.md's GIN tsvector index on `projects(name || pitch)` even though `/search` is not exposed in Spec 1. Low cost now, zero migration in Spec 2 when `/search` lands.

### Migrations

One initial Alembic migration `0001_foundation.py` creates all 17 tables plus the stack-items seed. From then on, one migration per feature. Autogenerated migrations are reviewed and edited before commit — never applied blindly.

---

## 4. Backend API

### Conventions

- All routes under `/api/v1/*`. Caddy rewrites `hangar.dev/api/*` → backend.
- Auth via httpOnly session cookie (`hangar_session`, SameSite=Lax, Secure, 30-day). Bearer tokens for CLI devices land in Spec 3.
- Request/response JSON. Pydantic v2 schemas in `backend/app/schemas/`.
- Errors as RFC 7807 Problem Details: `{ "type": "/errors/...", "title": ..., "status": ..., "detail": ... }`.
- Pagination cursor-based: `?cursor=<opaque>&limit=50` → `{ items, next_cursor }`.
- Every writing route logs to `audit_log` via SQLAlchemy session event listener (see §5).
- Rate limits via Redis token bucket: 60 req/min per session (general), 10 req/min per IP (auth endpoints).

### Endpoints in Spec 1

**Auth**
```
POST   /api/v1/auth/magic-link          { email }                   → 202 (no enumeration)
GET    /api/v1/auth/verify?token=       → sets cookie, 302 to /
POST   /api/v1/auth/logout              → clears cookie
```

**Me & Workspaces**
```
GET    /api/v1/me                       → { user, active_workspace, workspaces[] }
GET    /api/v1/workspaces               → [{ slug, name, role, plan }]
POST   /api/v1/workspaces               { slug, name }              → workspace
GET    /api/v1/workspaces/:slug         → full workspace
PATCH  /api/v1/workspaces/:slug         { name? }
```

**Projects**
```
GET    /api/v1/projects?status=&tag=&q=&cursor=&limit=
POST   /api/v1/projects                 { slug, name, emoji?, pitch?, status? }
GET    /api/v1/projects/:slug           → full project aggregate (repos, envs, infra, context, links, commands, stack, tags)
PATCH  /api/v1/projects/:slug           partial update
DELETE /api/v1/projects/:slug           → 204 hard delete, cascades
POST   /api/v1/projects/:slug/switch    → sets active_project
```

**Project children (sub-resources)**
```
GET    /api/v1/projects/:slug/context
PATCH  /api/v1/projects/:slug/context

POST   /api/v1/projects/:slug/repos              { role, git_url, default_branch?, local_path?, primary_lang?, license? }
PATCH  /api/v1/projects/:slug/repos/:id
DELETE /api/v1/projects/:slug/repos/:id

POST   /api/v1/projects/:slug/environments       { kind, url, env_template_path?, db_alias? }
PATCH  /api/v1/projects/:slug/environments/:id
DELETE /api/v1/projects/:slug/environments/:id

PATCH  /api/v1/projects/:slug/infra              upsert-style: any combination of fields

POST   /api/v1/projects/:slug/links              { kind, label, url }
PATCH  /api/v1/projects/:slug/links/:id
DELETE /api/v1/projects/:slug/links/:id

POST   /api/v1/projects/:slug/commands           { label, command, run_in?, confirm_required? }
PATCH  /api/v1/projects/:slug/commands/:id
DELETE /api/v1/projects/:slug/commands/:id

POST   /api/v1/projects/:slug/stack              { stack_item_slug, role? }
DELETE /api/v1/projects/:slug/stack/:stack_item_slug

POST   /api/v1/projects/:slug/tags               { tag_id }   or   { name, color } to create-and-attach
DELETE /api/v1/projects/:slug/tags/:tag_id

POST   /api/v1/projects/:slug/repo/resync        → re-fetch metadata from GitHub for linked repo
```

**Catalog**
```
GET    /api/v1/stack-items?q=&kind=
GET    /api/v1/tags
POST   /api/v1/tags                     { name, color }
```

**Integrations (GitHub only in Spec 1)**
```
GET    /api/v1/integrations                               → [{ kind, connected_at, config.masked }]
GET    /api/v1/integrations/github/oauth-start            → 302 to github.com/login/oauth/authorize
GET    /api/v1/integrations/github/oauth-callback         → exchanges code, stores encrypted token, 302 /import/github
DELETE /api/v1/integrations/github                        → revoke + delete row
GET    /api/v1/integrations/github/repos?page=&q=         → proxy GitHub API, normalized list
POST   /api/v1/integrations/github/import                 { repos: [{ owner, name, as_slug? }] } → [{ slug, status }]
```

**Health**
```
GET    /api/v1/healthz                  → { ok, version, db, redis }
```

### Validation rules

- Slug regex: `^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$` (2–50 chars, lowercase, no leading/trailing hyphen).
- Reserved slugs (both workspace and project): `api`, `admin`, `public`, `app`, `www`, `import`, `settings`, `billing`, `auth`.
- URL fields validated with `pydantic.HttpUrl`.
- Emoji field: optional; when present, matches a single `\p{Emoji}` code point (regex) — exactly one emoji.
- Status field: Pydantic Literal type, enforced at schema boundary.

### DI pattern

```python
async def endpoint(
    ws: WorkspaceContext = Depends(require_workspace),     # validates session, loads workspace
    project: Project    = Depends(get_project_by_slug),    # 404 if absent, asserts ws match
    db: AsyncSession    = Depends(get_db),
):
    ...
```

Active workspace comes from the user's session payload. A header `X-Workspace-Slug` can override when (Spec 4+) a user belongs to multiple workspaces.

### OpenAPI & client generation

FastAPI auto-generates `openapi.json`. CI step runs `openapi-typescript` → `frontend/src/api/types.ts`. The frontend API client is a thin `fetch` wrapper using these types — zero hand-written schema duplication.

---

## 5. Auth & Crypto

### Magic-link flow

```
1. POST /api/v1/auth/magic-link { email }
   → rate-limit 3/hour per email, 10/hour per IP (Redis token bucket)
   → always returns 202 (no user enumeration)

2. Backend creates magic_link_tokens row:
   { id, email, token_hash = sha256(random 32 bytes), expires_at = now + 15 min, consumed_at = null }
   → sends email via Resend:
     https://hangar.dev/auth/verify?token=<raw>

3. User clicks link → GET /api/v1/auth/verify?token=
   → hash lookup; checks expires_at and consumed_at
   → if first-time login:
       create users row
       create default workspace (slug derived from email local-part, sanitized, uniqueness-incremented)
       create workspace_members (role='owner')
       create workspace_keys with freshly generated DEK
   → mark consumed_at = NOW()
   → generate session_id (ULID), store in Redis (key: session:<id>, TTL 30 days, value: { user_id, workspace_id })
   → set cookie: hangar_session=<id>; HttpOnly; Secure; SameSite=Lax; Max-Age=2592000; Path=/
   → 302 to /

4. Every authenticated request:
   → middleware reads cookie, Redis lookup, loads user+workspace into request.state
   → if not found or expired: 401, clear cookie
```

Sessions are Redis-only (no Postgres table) — auto-expiry, no GC, Redis AOF survives restart.

### Default workspace naming

`email.split('@')[0]`, lowercased, restricted to `[a-z0-9-]`, truncated to 20 chars. Uniqueness conflict → append `-2`, `-3`, etc. Default name = that slug, title-cased. Owner may rename in Settings.

### Crypto for GitHub token

Per-workspace DEK (data encryption key):

- DEK: 32 random bytes, generated at workspace creation, stored as AES-256-GCM ciphertext in `workspace_keys.dek_ciphertext`, encrypted with `HANGAR_MASTER_KEY` from env.
- `HANGAR_MASTER_KEY`: 32 random bytes, base64-encoded, set in `/etc/hangar/hangar.env`, root:root 600.
- `integrations.token_ciphertext`: GitHub access token AES-256-GCM-encrypted with workspace DEK. Nonce prepended to ciphertext. Algorithm tag in `workspace_keys.algorithm` (currently `aes-256-gcm-v1`).

Spec 1 is **not end-to-end encrypted** — the server can decrypt tokens. This is the cost of operating without a user-derived key (no passkey yet). Spec 4 will introduce user-derived keys (passkey-derived master) and migrate workspace DEKs to envelope-encrypt with a passkey-scoped KEK. The `algorithm` field makes this migration trivial.

### CSRF

Session cookie is `SameSite=Lax` — default-safe against cross-site POSTs. In addition, mutating endpoints (POST/PATCH/DELETE) require `Origin: https://hangar.dev` (or `http://localhost:3000` in dev). No separate CSRF token — redundant with these controls for our surface.

### Audit logging

SQLAlchemy `before_flush` listener inspects `session.new`, `session.dirty`, `session.deleted`. For each non-`AuditLog` instance, emits an `AuditLog` row with:

- `workspace_id` from context-var set by auth middleware
- `actor` = `ui:<user_id>` (Spec 3 adds `mcp:<device_id>`; workers use `worker:<kind>`)
- `op` = `create | update | delete`
- `entity` = `__tablename__`
- `entity_id` = `obj.id`
- `diff` = JSONB of changed fields (only the delta — old + new)

Context-vars use `contextvars.ContextVar`. Tests assert that every write produces an audit entry.

### Secrets inventory

`/etc/hangar/hangar.env` (root:root, 600):

```
HANGAR_MASTER_KEY=<32-byte-base64>
HANGAR_DATABASE_URL=postgresql+asyncpg://hangar:...@postgres:5432/hangar
HANGAR_REDIS_URL=redis://redis:6379/0
HANGAR_RESEND_API_KEY=re_...
HANGAR_GITHUB_CLIENT_ID=...
HANGAR_GITHUB_CLIENT_SECRET=...
HANGAR_BASE_URL=https://hangar.dev
HANGAR_COOKIE_DOMAIN=hangar.dev
HANGAR_SESSION_MAX_AGE=2592000
HANGAR_SENTRY_DSN=                # optional, blank ok
```

Rotation: rewrite the file + `docker compose restart backend`. No in-app secret-management UI in Spec 1.

---

## 6. Frontend

### Tech

- Vue 3.5+ with `<script setup>`, TypeScript (strict), Vite 5
- Pinia for state
- Vue Router 4
- Tailwind 3 + shadcn-vue components
- Lucide Icons (strokewidth 1.5 default)
- **Geist Sans** + **Geist Mono** self-hosted (woff2 in `assets/fonts/`, preload in `index.html`)

### Routes

```
/                                    redirects to /p or /login
/login                               email input → magic-link sent
/auth/verify?token=                  callback, sets cookie, redirects
/p                                   all-projects index
/p/new                               quick-add modal over /p
/p/:slug                             project detail
/p/:slug/edit                        full-edit form over detail
/p/:slug/infra                       infra tab
/p/:slug/links                       links tab
/p/:slug/commands                    commands tab
/p/:slug/stack                       stack + tags tab
/import/github                       GitHub import screen
/settings                            account + workspace
/settings/integrations               GitHub connect / disconnect
```

### Three-pane project detail layout

```
┌─────────────────────────────────────────────────────────────────┐
│ ◈ lenny / butlr              switch…  ⌘K          (user menu)  │   44px top bar (glass)
├────────────┬──────────────────────────────────────┬─────────────┤
│ [ sidebar  │  🛎️ butlr                  ● building │ // telemetry│
│   project  │  openclaw-as-a-service               │   repo info │
│   list +   │                                      │   domain    │
│   status   │  [ focus card                    ]   │   server    │
│   dots ]   │  [ stack        ] [ infra        ]   │ // outbound │
│            │  [ context editor                ]   │   → links   │
│            │  [ links + commands (tabs)       ]   │             │
└────────────┴──────────────────────────────────────┴─────────────┘
  200px            1fr main                           240px
```

### Cmd+K palette

Hotkey `⌘K` / `Ctrl+K`. Centered modal 640px, glass background, backdrop-blur. Two sections:

- **PROJECTS** — fuzzy-matched list of workspace projects (name + slug), each shows status + days-since-touch
- **ACTIONS** — `+ new project` (N), `import from github` (I), `settings` (,)

Keyboard: ↑↓ nav, ⏎ select, ⌘+N direct-new, Esc close. Selection calls `POST /projects/:slug/switch` then navigates to `/p/:slug`. Signature touch: a mono `>` prompt prefix on the input.

### Quick-add modal

Fields: Name (required, auto-derives slug), Slug (editable, uniqueness-check on blur), Emoji (native picker), Status (dropdown, default 'building'), Pitch (optional). Optional expand: "Link a GitHub repo" pulls up an inline repo-picker.

### Project detail — 5 regions

1. **Hero** — emoji (36 px), name, pitch, status pill (click → status dropdown), edit button.
2. **Focus card** (col-span-2) — `current_focus` inline-editable, then `next_step`, then `user_wants` (collapsed by default). `blocked_by`, when set, renders as a red banner at the top.
3. **Stack card** — chip list, `+ add` → fuzzy-search `/stack-items`. New stack items may be created from the input (auto-added to the global catalog as `custom: true`).
4. **Infra card** — read-only key/value display with edit button → `/p/:slug/infra` tab.
5. **Links + commands card** — tab switcher inside one card. Links = list with kind-icon + label + external-link icon. Commands shows only labels in Spec 1 — execution is Spec 3.

### Right rail (telemetry)

Spec 1 shows what's actually backed:

- Git URL, default branch (from `project_repos`)
- Primary domain, server alias (from `project_infra`)
- Last updated_at

The uptime / SSL / commits / issues fields are rendered as `—` with a subtle hint "Health monitoring activates in a later release". No placeholders that lie.

### Pinia stores

- `useAuthStore` — user, workspaces, active_workspace_slug
- `useProjectsStore` — project list (cached), individual project fetch, CRUD with optimistic update + rollback
- `useCommandPaletteStore` — open state, query, results, selected index
- `useToastStore` — toast notifications

Stores are thin. No business logic. Pure state + API calls via typed client.

### API client

`frontend/src/api/client.ts` wraps `fetch` with the OpenAPI-generated types. Result pattern — no exceptions on 4xx:

```ts
const { data, error } = await api.GET('/api/v1/projects/{slug}', { params: { path: { slug } } });
```

### Empty states

1. `/p` empty → "Your hangar is empty." + primary [Import from GitHub] (only when not yet connected) + secondary [+ New project].
2. `/p/:slug` no context → "No focus set. [Set focus]".
3. `/import/github` no connection → "Connect GitHub to see your repos" + OAuth button.

### Loading, error, a11y

- **Loading:** skeleton screens in all three panes. No spinner longer than 200 ms without a skeleton.
- **Network loss:** top banner with retry; Pinia subscribes to `online`/`offline` and fetch failures.
- **401:** clear cookie, redirect to `/login`.
- **Error boundary** on page-level catches render errors: "Something broke, [reload] or [go home]."
- **A11y:** focus trap in modals; every action keyboard-reachable; aria-labels on icon-only buttons; semantic HTML; `prefers-reduced-motion` respected (transitions 0 ms).

### Responsive

Spec 1 is desktop-only (down to 1024 px). Smaller viewports render a "use desktop for now" landing. Responsive polish comes later — not critical to the operator-vibecoder use case.

### Dark-only

No light-mode in Spec 1. Add when user demand is real.

---

## 7. Visual System — Cockpit

### Colour palette

```
/* base */
--bg-body:         radial-gradient(ellipse at 20% -10%, #142132 0%, #070b10 55%)
--bg-surface:      rgba(20, 33, 50, 0.45)    /* glass cards */
--bg-surface-hi:   rgba(20, 33, 50, 0.65)    /* hover */
--bg-overlay:      rgba(7, 11, 16, 0.8)      /* modal backdrop */
--bg-chrome:       rgba(13, 18, 26, 0.7)     /* top bar, sidebar */

/* foreground */
--fg-primary:      #ffffff
--fg-body:         #cfd4dc
--fg-muted:        #8ba1bd
--fg-subtle:       #5e7088
--fg-disabled:     #3d4a5c

/* accents — phosphor signal */
--signal-green:    #5cc8a4    --signal-green-bg: rgba(92, 200, 164, 0.12)
--signal-amber:    #f5b84a    --signal-amber-bg: rgba(245, 184, 74, 0.12)
--signal-red:      #ff5b5b    --signal-red-bg:   rgba(255, 91, 91, 0.12)
--signal-blue:     #8ab4ff    --signal-blue-bg:  rgba(138, 180, 255, 0.08)

/* borders */
--border-subtle:   rgba(138, 180, 255, 0.08)
--border-default:  rgba(138, 180, 255, 0.12)
--border-strong:   rgba(138, 180, 255, 0.18)
```

Status → color:

| Status | Colour |
|---|---|
| idea | fg-muted, no dot |
| building | signal-green |
| live | signal-green (brighter, with glow) |
| paused | signal-amber |
| shipped | signal-blue |
| archived | fg-subtle |
| dead | signal-red (muted) |

### Typography

```
Sans:  "Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
Mono:  "Geist Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace

Scale:
  display   28 px  / 1.1  / -0.03em  / 600    hero
  title     20 px  / 1.2  / -0.02em  / 600    project name
  section   14 px  / 1.4  / -0.01em  / 600    card header
  body      13 px  / 1.5  /  0       / 400    default
  small     12 px  / 1.4  /  0       / 400    metadata
  micro     11 px  / 1.3  / +0.02em  / 500    uppercase labels (mono)
  code      12 px  / 1.5  /  0       / 400    monospace
```

**Signature:** every label above a card is **mono + uppercase + 11 px + letter-spacing 0.08em + `--fg-muted`**. This is the cockpit idiom.

### Spacing (8 px grid, 4 px sub-grid allowed for dense areas)

```
--space-1: 4   --space-2: 8    --space-3: 12   --space-4: 16
--space-5: 24  --space-6: 32   --space-7: 48   --space-8: 64
```

### Radius

```
--radius-sm: 3 px    pills, chips, mono-labelled elements (sharp)
--radius-md: 6 px    inputs, buttons
--radius-lg: 8 px    cards
--radius-xl: 12 px   modals, panels
```

Cockpit principle: soft cards, sharp pills.

### Depth

```
--shadow-card:    0 0 0 1px var(--border-default)
--shadow-card-hi: 0 0 0 1px var(--border-strong), 0 4px 20px rgba(0,0,0,0.3)
--shadow-modal:   0 24px 48px rgba(0,0,0,0.6), 0 0 0 1px var(--border-default)
--glow-signal:    0 0 6px currentColor
```

No drop-shadow on cards. Depth = border + backdrop-blur + gradient. Modals may use real shadow.

### Glass effect

```css
.glass {
  background: var(--bg-surface);
  backdrop-filter: blur(10px) saturate(1.2);
  border: 1px solid var(--border-default);
}
```

Applies to top bar, sidebar, cards, modals. Fallback for browsers without `backdrop-filter`: raise the bg alpha.

### Components

Shadcn-vue foundation (custom-themed to Cockpit): Button, Input, Textarea, Label, Dialog, DropdownMenu, Command, Toast, Tabs, Popover, ScrollArea, Select, Badge, Skeleton.

Custom (we build):

- `ProjectCard` — sidebar item with emoji, status dot, name, days-since-touch
- `StatusPill` — maps from status enum
- `ContextCard` — inline-editable focus/next/user-wants block
- `StackChip` — addable chip for stack items
- `LinkList` — kind icon + label + external icon
- `MonoLabel` — the cockpit signature label
- `EmptyState` — centred prompt with primary + secondary CTA
- `DataRow` — label / value two-column grid for telemetry rail
- `KbdHint` — keyboard shortcut pill

### Motion

```
--ease-out:  cubic-bezier(0.22, 1, 0.36, 1)
--ease-in:   cubic-bezier(0.64, 0, 0.78, 0)
--dur-fast:  120ms    hover, focus
--dur-med:   200ms    modal open, tab switch
--dur-slow:  300ms    page transition
```

`prefers-reduced-motion` → all durations 0 ms.

### Impeccable details (commits)

1. Tabular data uses `font-variant-numeric: tabular-nums` in non-mono contexts for column alignment.
2. Path separators (`lenny / butlr`) render in `--fg-subtle`.
3. Sidebar emojis have `filter: saturate(0.85)` default, `saturate(1)` on active.
4. Links (`a.link`) default to `border-bottom: 1px dashed var(--signal-blue-bg)` — no underline. Hover solidifies the border and brightens text.
5. Card hover: `--border-subtle` → `--border-default`, bg `surface` → `surface-hi`. 120 ms. No scale or shadow — restraint.
6. Status pills: coloured dot on the left (6 px), 4 px margin-right, pill bg is the color's `-bg` alpha, text in solid color.
7. Cmd+K modal input has a **mono `>` prompt prefix**. Small gesture, strong character.

### Visual-audit checklist (lives in `docs/visual-audit.md` once built)

- [ ] No default browser fonts visible on any critical path (login, dashboard, modals).
- [ ] All tabular data uses `tabular-nums`.
- [ ] Every interactive element has hover + focus + disabled states.
- [ ] Responsive down to 1024 px. Below that, "use desktop" landing.
- [ ] Dark-mode only; no `prefers-color-scheme: light` fallback in Spec 1.

---

## 8. Error Handling, Testing, Deployment

### Error handling

**Backend (three tiers):**

1. **Validation** (Pydantic) → 422 Unprocessable, field-level details
2. **Business** (service layer) → 400 / 404 / 409 with Problem+JSON
3. **Infra** (DB, Redis, HTTP) → 503 Service Unavailable, logged + Sentry-hook-ready

Every error class inherits from `HangarError(detail, status, type)`. FastAPI exception handler maps to RFC 7807. Uncaught exceptions → 500, stack trace logged, user sees generic "Something broke" without internals.

**Frontend:**

- Non-blocking errors → toast
- Field-level validation (422) → inline error below the field
- Auth loss (401) → redirect to `/login`
- Network loss → top banner with retry
- Render error → page-level error boundary: "Something broke, [reload] or [go home]"

Optimistic updates rollback on error: snapshot → mutate → API → on error, restore snapshot + toast.

### Testing

| Layer | Tool | Against | Coverage |
|---|---|---|---|
| Backend unit | pytest | pure functions | where logic is non-trivial |
| Backend integration | pytest + real Postgres | API routes, DB ops, auth | every endpoint has ≥1 happy + ≥1 error test |
| Backend auth | pytest | magic-link + session + audit | full flow, expiry, replay rejection |
| Frontend unit | Vitest | components, composables, stores | interactive components only |
| Frontend integration | Vitest + MSW | page flows | login, project-create, switch, edit-context |
| E2E | Playwright | full stack via docker-compose.dev | **3 scenarios:** signup → create project → view detail; import from GitHub; edit context + verify audit |

No DB mocks. Pytest fixture spins up an empty Postgres schema per test function (transaction-rollback pattern). Real SQL against real Postgres — schema drift fails loud.

### CI

```yaml
jobs:
  backend:
    services: postgres:16, redis:7
    steps: [ruff check, mypy --strict, pytest -v]
  frontend:
    steps: [pnpm typecheck, pnpm lint, pnpm test, pnpm build]
  e2e:
    needs: [backend, frontend]
    steps: [docker compose up -d, playwright test]
  deploy:
    if: branch == main && all-green
    steps: [buildx push, ssh hangar-prod ./deploy.sh <sha>]
```

### `deploy.sh`

```bash
#!/bin/bash
set -euo pipefail
SHA=$1
export HANGAR_SHA=$SHA
docker compose pull
docker compose run --rm backend alembic upgrade head
docker compose up -d --no-deps backend frontend
sleep 3
curl -fsS http://localhost:8000/healthz || {
  echo "Health check failed, rolling back"
  export HANGAR_SHA=$(cat /srv/hangar/.last-good-sha)
  docker compose up -d --no-deps backend frontend
  exit 1
}
echo "$SHA" > /srv/hangar/.last-good-sha
```

### Monitoring (Spec 1 minimum)

- `docker compose logs` + journalctl
- `/api/v1/healthz` returns DB + Redis status
- External uptime monitor (UptimeRobot free) pings every 5 min
- Sentry hook ready in backend (env var `HANGAR_SENTRY_DSN`, no-op when blank)
- Prometheus/Grafana deferred to Spec 4

### Backup

- Nightly cron: `pg_dump` → encrypted tar → Hetzner Object Storage (separate region)
- Retention: 7 daily + 4 weekly + 3 monthly
- Quarterly restore-drill — manual, executed once in Spec 1 build-out to verify

---

## 9. Open Questions (none blocking Spec 1)

- **Custom stack items**: in Spec 1 any user can add a new `stack_items` row via the chip creator. They land with `custom: true`. Should we curate promotion to "official" in a later spec? → Decision deferred; no blocker now.
- **Slug collisions on GitHub import**: if imported repo name matches an existing project slug, the import endpoint returns `status: 'skipped'` and exposes the conflict in the response. UI offers an "as slug" rename field per conflicted row.
- **Audit-log retention**: unlimited in Spec 1. Rotation policy (e.g., "archive rows older than 180 days to cold storage") decided with Spec 4 when compliance features land.
- **Rate-limit tuning**: 60 req/min is conservative. We'll revisit once we have real usage data in Spec 2/3.

## 10. Build order (high level; detailed plan comes from writing-plans)

The plan-writing skill will expand this into discrete, sequenceable tasks. Rough order:

1. Monorepo skeleton + `docker-compose.dev.yml` + Caddy config + env templates
2. Alembic migration `0001_foundation.py` with all 20 tables + stack-items seed
3. Backend: config, DB, Redis, crypto module, audit listener, auth middleware
4. Auth endpoints: magic-link request + verify + logout; Resend integration
5. Me & workspaces endpoints; workspace auto-creation on first login
6. Projects CRUD + children (repos, envs, infra, context, links, commands, stack, tags)
7. GitHub integration endpoints (OAuth start/callback, repos list, bulk import, re-sync)
8. Pydantic schemas + OpenAPI + client-type-generation step in CI
9. Frontend skeleton: Vue app, Pinia stores, Vue Router, typed API client, Tailwind + tokens.css
10. Auth pages (login, verify)
11. Dashboard pages: `/p` index, `/p/:slug` three-pane detail
12. Cmd+K palette with project switcher + actions
13. Quick-add modal + full-edit form + tabs (infra / links / commands / stack)
14. GitHub import page (OAuth connect, repo-picker, bulk import)
15. Settings pages (account, workspace, integrations)
16. E2E Playwright scenarios
17. Production deploy: Hetzner VPS provisioning, Caddy, docker-compose, env secrets, first deploy
18. Backup cron + uptime monitor + quarterly restore drill

---

**End of Spec 1 design.**
