<div align="center">

# Vibecell

**The operating system for vibecoders.**

A single source of truth for every project you're shipping — context, decisions,
sessions, secrets, environments — wired straight into Claude Code via a local MCP server.

[![Status](https://img.shields.io/badge/status-building-c45d3e)](https://vibecell.dev)
[![Made with](https://img.shields.io/badge/made_with-Claude_Code-D97757)](https://claude.com/claude-code)

[Website](https://vibecell.dev) · [Spec](HANGAR.md) · [Security](SECURITY.md)

</div>

---

## What it does

You start every Claude Code session and Claude already knows:

- What you were doing last (current focus, next step, last 3 commits).
- Why you decided what you decided (ADR-lite log, searchable in seconds).
- Which environments exist, which secrets are needed, where they live.
- What todos are open, what's blocked, what shipped this week.

No re-onboarding the model. No copy-pasting `.env` keys into prompts.
No Notion-page archaeology. Just `vibecell_active()` and Claude is up to speed.

When you commit, Claude logs the session. When you ship, Claude writes the
changelog. When you pivot, Claude updates the focus. The dashboard at
[vibecell.dev](https://vibecell.dev) stays in sync — you watch progress
tick off in real time instead of staring at a wall of silent code edits.

## Highlights

- **MCP-first.** ~50 tools cover project context, todos, decisions, sessions,
  secrets, ship events. Claude calls them automatically — no slash commands.
- **Secrets vault.** Inline-encrypted (workspace DEK) or by reference
  (`op://`, `bw://`, `ssh-agent://`, `env://`). Values never leave your machine
  when stored as references.
- **Ship Loop.** Commit → auto-log session → mark todos done → tag release
  → render changelog. End-to-end, hands off.
- **Local-first.** Daemon binds `127.0.0.1:7421`. Your data lives in
  `~/.hangar/`. Cloud-sync is opt-in.
- **Drift detection.** Repo manifests are SHA-256 fingerprinted. New deps,
  removed packages, infra changes — Claude notices on the next session start.

## Quick start

Install the CLI:

```bash
curl -LsSf https://vibecell.dev/install.sh | sh
hangar daemon start
```

Then add this to your project's `.mcp.json` (or your global Claude Code config):

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

Read the token from `~/.hangar/mcp-token` and export it as `HANGAR_MCP_TOKEN`.

In Claude Code, run `vibecell_create_project` to scaffold your first project,
or `vibecell_active` if one already exists. From there, Claude takes over.

Full setup walkthrough: [vibecell.dev/docs/getting-started](https://vibecell.dev/docs/getting-started).

## Architecture

```
┌──────────────┐   MCP/HTTP   ┌────────────────┐
│ Claude Code  │ ───────────► │  hangar daemon │  ← local-only
└──────────────┘   :7421      │  (Python)      │
                              └────────┬───────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
    ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
    │ Postgres     │          │ Vue 3 + Vite │          │ Rust CLI     │
    │ (state)      │          │ (dashboard)  │          │ (hangar bin) │
    └──────────────┘          └──────────────┘          └──────────────┘
```

| Component | Stack | Purpose |
|---|---|---|
| `cli/` | Rust | `hangar` binary, daemon control, install path |
| `backend/` | Python (FastAPI, uv, SQLAlchemy) | MCP HTTP server, business logic |
| `frontend/` | Vue 3 + Vite + Tailwind | Local dashboard at `vibecell.dev` |
| `ops/` | Docker Compose, scripts | Local + production deploy |
| `docs/` | Specs and implementation plans | Source-of-truth for the build |

## Dev quickstart

```bash
docker compose -f ops/docker-compose.dev.yml up -d
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000
cd frontend && pnpm install && pnpm dev
```

Open <http://localhost:3000> — it proxies `/api` to the backend.

The full spec — every tool, schema, ship-loop state machine — lives in
[HANGAR.md](HANGAR.md). Read it before non-trivial changes.

## Why "hangar" everywhere internally

The project shipped under the working title "Hangar" before the public brand
became Vibecell. The CLI binary, env-var prefix (`HANGAR_`), config dir
(`~/.hangar/`), package names, and MCP tool names all stay `hangar*` —
they're developer-facing and renaming would churn every user's setup.

## Contributing

This is a solo-builder tool first; PRs are welcome but the bar is high — read
[HANGAR.md](HANGAR.md) and align with the architectural decisions there.
Issues, ideas, and bug reports are always appreciated.

For security findings, see [SECURITY.md](SECURITY.md) — please don't open a
public issue for vulnerabilities.

## License

License TBD. Until one is chosen explicitly, default copyright applies — code
here is source-available for review and personal use, but please don't
redistribute or fork until a license file lands.
