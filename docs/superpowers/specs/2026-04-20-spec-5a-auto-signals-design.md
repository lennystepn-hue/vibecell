# Spec 5A — Auto-Signals Design

**Date**: 2026-04-20  
**Status**: Scaffolded (MVP stubs committed)  
**Owner**: vibecell.dev core

---

## Overview

Spec 5A gives vibecell the ability to automatically collect signals about each project — without the user having to manually update context. Currently a project's health, cost, and domain status are entirely manual. Auto-Signals changes this: the system continuously polls, ingests, and summarises the state of every project so the user gets accurate, up-to-date information in their MCP context.

The key insight is that most of this data already exists elsewhere — uptime checks, GitHub activity, Stripe billing, cloud provider dashboards. Vibecell becomes the aggregation point.

---

## 1. Health Checks

### Design

Every project with a `healthcheck` kind `ProjectLink` gets probed every 5 minutes. Results are written to `project_health_events`. A summarised view is maintained in `project_health_summary`, refreshed every 15 minutes.

### Database

**`project_health_events`** — raw probe results:
- `id` (ULID PK), `project_id` (FK → projects), `probed_at` (timestamptz), `status` (`up | down | timeout | error`), `http_status_code` (int, nullable), `latency_ms` (int, nullable), `error_msg` (text, nullable)

**`project_health_summary`** — aggregated view per project:
- `project_id` (PK, FK → projects), `last_status` (`up | down | unknown`), `last_probed_at` (timestamptz), `uptime_24h_pct` (float, nullable), `uptime_7d_pct` (float, nullable), `avg_latency_ms` (int, nullable), `updated_at` (timestamptz)

### Probe Logic

`health_monitor.probe_all()` is called every 5 minutes by APScheduler. It:
1. Queries all projects with a `healthcheck` link (via `ProjectLink.kind = 'healthcheck'`).
2. For each, sends a `GET` request via `httpx.AsyncClient` with `timeout=10s`.
3. Records the result in `project_health_events`.
4. Every 15 minutes, a separate job recalculates `project_health_summary` per project.

### HTTP Probe Rules

- HTTP 2xx = `up`
- HTTP 5xx = `down`
- Connection refused / DNS failure = `error`
- Timeout after 10s = `timeout`
- Redirects followed (up to 3).

### Rate Limiting

Maximum 50 concurrent probes. Use `asyncio.Semaphore(50)`. Projects are probed in workspace-batched order to avoid thundering herd.

---

## 2. Cost Attribution

### Design (deferred — Phase 5A.2)

Pull cost data from three sources:
- **Stripe** — aggregate billing across Pro workspaces.
- **OpenAI / Anthropic** — API usage via their usage APIs, tagged with project metadata if possible.
- **Hetzner** — server cost allocation by label/tag. Monthly pull.

Cost data is attributed to projects via `workspace_id + project_id` tags configured in each provider's dashboard. A nightly job pulls and stores to a `cost_attribution` table (not yet created — deferred).

---

## 3. Domain Inventory

### Design (deferred — Phase 5A.3)

Enumerate domains from DNS providers (Cloudflare / Route53). Store per workspace:
- Domain name, expiry date, registrar, nameservers.
- Auto-match to existing projects by hostname pattern.
- Alert on domains expiring in < 30 days.

Deferred until DNS provider API integrations are scoped. Spec 5A.3.

---

## 4. Detector Signals

### Design

Beyond raw uptime, synthesise higher-level signals from existing data:

| Signal | Source | Refresh |
|--------|--------|---------|
| Commits in last 7 days | GitHub API (existing integration) | 1h |
| Open issues count | GitHub API | 1h |
| Last ship date | `ships` table | real-time |
| Last session date | `sessions` table | real-time |
| Uptime % (24h, 7d) | `project_health_events` | 15min |
| Days since last activity | ships + sessions + decisions + notes | 15min |

These signals feed into the `project_health_summary` JSONB `signals` column (deferred) and into the Portfolio-Intel spec (5B) for stagnation detection.

---

## 5. Frontend — ProjectHealthCard

A compact card showing the current health status of a project. Displayed in `ProjectDetail` alongside the existing cards.

### Visual Design

- Traffic light: green (up) / red (down) / grey (unknown / not configured).
- Last probe timestamp, latency in ms.
- Uptime % over 24h and 7d.
- "Not configured" state with a link to add a healthcheck URL.

### Data

`GET /api/v1/projects/{slug}/health` returns the latest `project_health_summary` row for the project. Returns 404 if no summary exists yet, or 200 with `{status: "unknown"}` if the project has no healthcheck link.

---

## 6. MCP Integration

The `vibecell_get` and `vibecell_active` MCP tools should include the latest health summary in their response payload so Claude can surface it without extra tool calls. Deferred to 5A implementation phase — requires updating the MCP response schemas.

---

## Architecture Decision: APScheduler vs Celery

We continue using APScheduler (already in use for oauth_cleanup) rather than introducing Celery. Rationale: the probe workload is I/O bound and async-friendly. APScheduler's async support handles it cleanly. If the fleet grows beyond ~500 projects, migrate to Celery workers. Record this decision.

---

## Implementation Phases

| Phase | Work | Est. |
|-------|------|------|
| 5A.1  | Health probe cron + DB write + summary calc (real impl) | 2d |
| 5A.2  | Cost attribution pull (Stripe + Hetzner) | 2d |
| 5A.3  | Domain inventory (Cloudflare API) | 2d |
| 5A.4  | MCP tool integration (include health in responses) | 1d |
| 5A.5  | Frontend polish (sparkline history, alert emails) | 1d |

---

## Open Questions

- Should probes run only for Pro workspaces or all? (Initial choice: all — it's cheap and provides value.)
- Probe from the VPS itself (Hetzner EU) — acceptable for most projects. Could add external probe from second region later.
- Where to alert on `down`? Email via Resend (already wired) is the natural path.
- Should `project_health_summary` be part of the MCP context auto-injected on `vibecell_active`?
