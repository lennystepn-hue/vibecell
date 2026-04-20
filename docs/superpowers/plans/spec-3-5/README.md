# Spec 3.5 — Remote MCP + OAuth 2.1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Execute phases in order; within a phase, execute tasks top-to-bottom.

**Spec:** [docs/superpowers/specs/2026-04-20-spec-3-5-remote-mcp-oauth-design.md](../../specs/2026-04-20-spec-3-5-remote-mcp-oauth-design.md)

**Goal:** Ship `https://vibecell.dev` as a public MCP server with OAuth 2.1 so Claude Desktop, Cursor, Zed, and any MCP client can connect zero-install. 17 remote tools (vibecell.run stays CLI-only). Workspace-scoped tokens, branded consent, unified connections/revocation UI.

---

## Phases

| Phase | File | Scope |
|-------|------|-------|
| 1 | [phase-01-oauth-server.md](phase-01-oauth-server.md) | DB migration 0005 + `oauth/` module (discovery, DCR, authorize, token, revoke) |
| 2 | [phase-02-mcp-endpoint.md](phase-02-mcp-endpoint.md) | `/mcp` Streamable HTTP + 17-tool dispatcher wired to backend services + audit log |
| 3 | [phase-03-frontend.md](phase-03-frontend.md) | Consent screen (`OAuthConsent.vue`) + Connections settings page (`Connections.vue`) + `/api/v1/connections` API |
| 4 | [phase-04-connect-button-docs.md](phase-04-connect-button-docs.md) | "Connect to Claude Desktop" modal + deep-link, dashboard CTA, docs page, Prometheus metrics |
| 5 | [phase-05-rollout.md](phase-05-rollout.md) | Production deploy, manual verification with real Claude Desktop, monitoring, announcement |

---

## Execution Order & Dependencies

```
Phase 1 (OAuth server)
   │
   ▼
Phase 2 (MCP endpoint)  ────────┐
   │                             │
   │                             │
   ▼                             ▼
Phase 3 (Frontend consent + connections)
   │
   ▼
Phase 4 (Connect button + docs)
   │
   ▼
Phase 5 (Production rollout)
```

Phase 2 depends on Phase 1's JWT issuance. Phase 3 depends on Phase 1 (consent endpoint) and Phase 2 (connections-API backend data). Phase 4 depends on Phase 3 (the connections page must exist to link to). Phase 5 depends on everything green.

## Commit Policy

- Every task ends with a commit. Never batch.
- Commit messages follow conventional-commits style: `feat(oauth): ...`, `test(mcp): ...`, `fix(frontend): ...`.
- Each phase ends with one summary commit describing the phase completion + a git tag `v0.X.Y-spec-3-5-phase-N` (do not tag until end-of-phase review passes).

## Testing Policy

- **TDD** for every new file: write failing test → run (FAIL) → write minimal impl → run (PASS) → commit.
- Coverage targets: ≥ 85% on `backend/app/oauth/` and `backend/app/mcp/`.
- Playwright E2E for consent + connections flows in Phase 3.
- Phase 5 manual verification uses real Claude Desktop against staging.

## Pre-flight Checks Before Starting

Run once before Phase 1:

```bash
cd backend && uv sync
cd backend && uv run alembic heads       # Expect one head (0004)
cd backend && uv run pytest -q           # Expect all green
cd frontend && pnpm install
cd frontend && pnpm test                 # Expect all green
```

If any step fails, stop and fix before beginning Phase 1.
