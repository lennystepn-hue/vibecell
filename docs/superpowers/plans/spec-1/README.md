# Spec 1 Implementation Plan — Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement the phase files below, one phase at a time.

**Goal:** Ship Hangar Spec 1 to production — auth + workspaces + projects + GitHub import + Cockpit-themed Vue dashboard, deployed to Hetzner at `hangar.dev`.

**Spec:** [docs/superpowers/specs/2026-04-18-spec-1-foundation-dashboard-design.md](../../specs/2026-04-18-spec-1-foundation-dashboard-design.md)

**Architecture:** Monorepo with `backend/` (FastAPI + SQLAlchemy-async + Alembic + Postgres + Redis), `frontend/` (Vue 3 + TS + Vite + Pinia + Tailwind + shadcn-vue), `ops/` (Docker Compose + Caddy). Magic-link auth via Resend; AES-256-GCM envelope crypto for GitHub tokens; audit log via SQLAlchemy before_flush listener. Production on single Hetzner CX22 VPS behind Caddy auto-TLS. TDD throughout against real Postgres — no DB mocks.

**Tech Stack:** Python 3.12, FastAPI 0.115+, SQLAlchemy 2 (async), asyncpg, Alembic, Pydantic v2, Redis 7, Postgres 16, uvicorn, Resend, pytest + httpx + testcontainers. Vue 3.5, TypeScript (strict), Vite 5, Pinia, Vue Router 4, Tailwind 3, shadcn-vue, Lucide, openapi-typescript, Vitest + MSW, Playwright. Caddy 2, Docker Compose, GitHub Actions.

---

## Phase order (strict dependency)

| # | Phase | File | Output |
|---|---|---|---|
| 0 | Repo Skeleton & Tooling | [phase-00-repo-skeleton.md](phase-00-repo-skeleton.md) | monorepo layout, `docker-compose.dev.yml`, empty FastAPI + Vue apps respond on ports |
| 1 | Database Foundation | [phase-01-database-foundation.md](phase-01-database-foundation.md) | 20 SQLAlchemy models, Alembic `0001_foundation` migration, stack seed, all pass integration tests against real Postgres |
| 2 | Core Utilities | [phase-02-core-utilities.md](phase-02-core-utilities.md) | config, ULID, crypto (AES-256-GCM), audit listener, Redis client, rate-limiter, exceptions |
| 3 | Auth | [phase-03-auth.md](phase-03-auth.md) | `/auth/magic-link`, `/auth/verify`, `/auth/logout`, session middleware, Resend integration |
| 4 | Workspaces & Me | [phase-04-workspaces-me.md](phase-04-workspaces-me.md) | `/me`, `/workspaces*`, first-login bootstrap (workspace + DEK) |
| 5 | Projects CRUD | [phase-05-projects-crud.md](phase-05-projects-crud.md) | `/projects*` list / create / get / update / delete / switch |
| 6 | Project Children | [phase-06-project-children.md](phase-06-project-children.md) | context, repos, environments, infra, links, commands, stack, tags sub-resources |
| 7 | Catalog & Tags | [phase-07-catalog.md](phase-07-catalog.md) | `/stack-items`, `/tags`, stack seed verification |
| 8 | GitHub Integration | [phase-08-github-integration.md](phase-08-github-integration.md) | OAuth start/callback, repos proxy, bulk import, resync |
| 9 | Frontend Foundation | [phase-09-frontend-foundation.md](phase-09-frontend-foundation.md) | Vue app, router, Pinia, typed API client, tokens.css, Geist fonts |
| 10 | Auth Pages | [phase-10-auth-pages.md](phase-10-auth-pages.md) | `/login`, `/auth/verify` pages + auth store |
| 11 | Dashboard | [phase-11-dashboard.md](phase-11-dashboard.md) | `/p` index, `/p/:slug` three-pane detail, Cockpit components |
| 12 | Command Palette | [phase-12-command-palette.md](phase-12-command-palette.md) | Cmd+K modal, project switcher, global hotkey |
| 13 | Forms & Modals | [phase-13-forms-modals.md](phase-13-forms-modals.md) | quick-add, full-edit, infra / links / commands / stack tabs |
| 14 | GitHub Import UI | [phase-14-github-import-ui.md](phase-14-github-import-ui.md) | `/import/github`, repo-picker with bulk select |
| 15 | Settings | [phase-15-settings.md](phase-15-settings.md) | `/settings`, `/settings/integrations` |
| 16 | E2E | [phase-16-e2e.md](phase-16-e2e.md) | 3 Playwright scenarios: signup+create, import, edit+audit |
| 17 | Production Deploy | [phase-17-production-deploy.md](phase-17-production-deploy.md) | Hetzner VPS provisioning, Caddy, compose, first deploy, backup cron, uptime ping |

---

## Working rules (all phases)

- **TDD, real DB.** Every backend test hits a real Postgres (via `testcontainers`) — no mocks.
- **One task = one commit.** Commit message format: `<type>: <summary>` where type ∈ {feat, fix, chore, docs, refactor, test, ci}.
- **Expected-output assertions.** Every "run this command" step states what the output must contain.
- **No skipped hooks.** Never `git commit --no-verify`.
- **Windows note.** Work on Windows via Bash — use forward slashes in all paths; commands are portable bash. `pnpm` and `uvicorn` are installed under the user's PATH after Phase 0.
- **Checkpoints.** End of each phase: all tests pass, `main` has a green CI run, phase-doc checkbox "Phase complete" gets ticked in the phase file.

---

## What "done" means (repeated from spec §1)

1. New user requests magic link, clicks it, lands on empty dashboard.
2. Empty state prompts GitHub connect or manual project creation.
3. GitHub OAuth stores encrypted token, opens repo-picker, bulk import creates N projects with auto-filled metadata.
4. Every field in the scoped tables is UI-editable with optimistic updates + audit-logged.
5. Cmd+K switches projects in < 100 ms perceived latency; persists `active_project`.
6. Dashboard runs in Cockpit visual language.
7. CI green on every merge to `main`; deploy-on-green to `hangar.dev`.
