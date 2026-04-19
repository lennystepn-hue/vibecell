# Spec 3 — CLI + MCP + Claude Skill

**Status:** design approved (2026-04-19)
**Scope:** Second of 5 Hangar specs (after Spec 1 — Foundation + Dashboard).
**Prerequisite:** Spec 1 shipped (http://89.167.111.89:8080 running, backend APIs stable).
**Parent:** [HANGAR.md](../../../HANGAR.md) §3.11, §6, §7, §8.

---

## 1. Goal

Turn Hangar from "a web dashboard you visit" into "the OS that Claude Code breathes through." Every coding session auto-loads project context at start and auto-writes a session summary + inferred next step at end. Secrets resolve locally via 1Password / Bitwarden / ssh-agent and never traverse the cloud.

## 2. Acceptance criteria

At the end of Spec 3, this happens:

1. Opening Claude Code in any repo auto-triggers `hangar.active()` via the Claude skill → Claude knows current focus, next step, open questions, last 3 sessions, stack, infra.
2. Saying "done" / "log this" at session end triggers `hangar.log_session()` → summary + files_touched + commits + inferred next_step posted to Hangar DB. Dashboard reflects it in < 1s.
3. Switching projects happens via `⌘K` in Claude Code's host (or `hangar switch <slug>`) — no tab-flipping.
4. Any saved command in Hangar (`Deploy`, `Tail logs`, `Backup now`) runs via `hangar run <label>`. Secrets referenced in the command auto-resolve via `op` / `bw` / ssh-agent at exec-time; values never touch stdout logs or cloud.
5. `hangar.dev` dashboard shows real-time session activity ("Claude active in butlr now, last output 14s ago").
6. Claude Code works offline-capable for reads (SQLite cache); writes queue and sync on reconnect.
7. Cross-platform: macOS (launchd), Linux (systemd --user), Windows (scheduled task). Static binary per platform, installed via `brew` / `scoop` / `curl | sh`.

## 3. Architecture

```
 ┌──────────────────┐       ┌────────────────────────────┐       ┌──────────────┐
 │  Claude Code     │◄─────►│   hangar daemon            │◄─────►│  hangar.dev  │
 │  (or any MCP     │  MCP  │   127.0.0.1:7421           │  WS   │   backend    │
 │   client)        │ HTTP  │                            │  REST │              │
 │                  │       │   ┌────────────────────┐   │       │              │
 │  Hangar skill    │       │   │  MCP server        │   │       │              │
 │  (markdown)      │       │   │  (rmcp)            │   │       │              │
 └──────────────────┘       │   └────────────────────┘   │       └──────────────┘
                            │   ┌────────────────────┐   │
                            │   │  Local cache       │   │
                            │   │  SQLite            │   │
                            │   └────────────────────┘   │
                            │   ┌────────────────────┐   │
                            │   │  Secret resolver   │   │
                            │   │  op / bw / ssh     │   │
                            │   └────────────────────┘   │
                            └────────────────────────────┘
                              ▲
                              │ CLI
                              ▼
                            hangar CLI commands
```

**Three physical deliverables:**
1. **`hangar` static Rust binary** — ~5MB, installed via `brew install hangar` / `curl -LsSf https://hangar.dev/install.sh | sh` / `scoop install hangar`
2. **`hangar` daemon** — managed by platform service (launchd / systemd / scheduled-task), hosts MCP on `127.0.0.1:7421`
3. **Hangar Claude skill** — single markdown file, auto-installed into `~/.claude/skills/hangar/SKILL.md` via `hangar skill install`

## 4. Key design decisions

### 4.1 Tech choices

| Concern | Choice | Why |
|---|---|---|
| Language | Rust (per HANGAR.md §11) | Static binary, small, good MCP lib, fast startup |
| Runtime | `tokio` | Async ecosystem standard |
| MCP | `rmcp` (modelcontextprotocol-rust-sdk) | Official Rust SDK |
| HTTP server | `axum` 0.7+ | Hooks into `tower`, `tokio-tungstenite` for WS later |
| HTTP client | `reqwest` | Cookies + JSON |
| DB | `rusqlite` + `tokio-rusqlite` wrapper | Embedded, zero-setup for users |
| Keychain | `keyring` crate (cross-platform: macOS Keychain / Linux secret-service / Windows Credential Manager) | Single API, native storage |
| Serialization | `serde` + `serde_json` | Standard |
| CLI parsing | `clap` 4 | Ergonomic derive macros |
| Cross-compile | `cross` + GitHub Actions matrix | Simplest CI-builds for 3 platforms |

### 4.2 Auth (device-code flow)

1. `hangar pair` → CLI calls `POST /api/v1/cli/pair/start` → backend returns `{device_code, user_code, verification_url, expires_in}`
2. CLI prints: "Open https://hangar.dev/cli/pair and enter code ABCD-EFGH" (and opens browser)
3. User confirms in browser (logged-in session) → backend associates device_code with user_id+workspace_id
4. CLI polls `POST /api/v1/cli/pair/complete {device_code}` every 2s → gets `{token, device_id}` on success
5. CLI stores `token` in OS keychain under service `hangar.dev`, account `<base_url>:<device_id>`
6. Subsequent API calls use `Authorization: Bearer <token>`
7. Rotation: `hangar pair --rotate` invalidates current token, issues new one.

Backend adds:
- `cli_devices` table already exists (Spec 1)
- New endpoints: `POST /cli/pair/start`, `POST /cli/pair/complete`, `DELETE /cli/devices/:id`
- Hangar-dashboard "Devices" settings page (Spec 3 extension, piggyback on existing `/settings`)

### 4.3 MCP transport

**HTTP on `127.0.0.1:7421`** — per HANGAR.md §7. Bearer-token auth (different from the CLI device token — generated at daemon start, short-lived).

Rationale for HTTP over stdio:
- Multi-client: Claude Code + Claude Desktop + Cursor + Zed can all connect the same daemon simultaneously
- Hot-reload: daemon restart doesn't kill client's MCP handshake per-se; clients reconnect
- Tool discovery via `mcp-inspector` trivial
- Remote debugging when needed (ssh port-forward to server for sanity checks)

Bearer token:
- Generated on daemon start, written to `~/.hangar/mcp-token` (mode 600)
- CLI command `hangar mcp-token` prints it — for pasting into client configs
- Rotatable via `hangar mcp-token --rotate`

### 4.4 Local-first cache

SQLite at `~/.hangar/cache.sqlite`. Schema mirrors the cloud (subset: projects, sessions, decisions, ideas, links, commands, stack, infra, context).

**Read path:**
- MCP tool call → daemon reads SQLite → returns (sub-ms)
- Timestamp on each row; if stale > 60s since last WS heartbeat, daemon fires a refresh

**Write path:**
- MCP tool call (write) → daemon writes to SQLite local + enqueues to cloud via WebSocket
- On cloud-ack, replaces the row with server copy (to capture server-assigned timestamps/IDs)
- Offline: writes queue in `~/.hangar/outbox/` as JSON files, replay on reconnect

**Sync strategy:**
- On daemon start: full pull of active workspace (projects + last 100 sessions + all decisions + current context) via REST
- WebSocket `/v1/ws` for live updates (project changes from web UI, other devices, background worker)
- Last-write-wins via server timestamps

### 4.5 Secret resolver (1Password-first)

**`project_secret_refs` table (already in Spec 1 migration as `project_secret_refs`, deferred):** activate now. Schema:
```sql
project_secret_refs (
  id TEXT PK, project_id FK, label TEXT, kind TEXT, reference TEXT
)
```
Where `kind ∈ {inline_encrypted, op, bw, ssh_agent, env_path, keychain}`.

**Mode A — inline_encrypted (Hangar-stored):**
- `hangar secret set stripe-key sk_test_...` (no `--ref`)
- Value encrypted with workspace DEK (existing Spec 2 crypto), stored in `integrations.token_ciphertext` or a new `secret_values` column
- Resolved by calling backend `GET /projects/:slug/secrets/:label` → returns plaintext over HTTPS, decrypted via DEK+master-key
- **Risk:** server can theoretically decrypt. Fine for dev-mode / convenience secrets.

**Mode B — op (1Password-referenced):**
- `hangar secret set stripe-key --ref op://Private/Stripe/api-key`
- Only reference string stored in Hangar DB
- CLI resolves: shell out to `op read op://Private/Stripe/api-key`
- Value written to OS clipboard with TTL; CLI clears clipboard after 45s
- Shown to Claude via `hangar.secret(label)` tool → returns `{resolved: true, delivery: "clipboard", ttl_seconds: 45}` — the value itself NEVER leaves the user's machine, never hits the MCP wire
- For `hangar run <label>` with saved commands like `ANTHROPIC_API_KEY=@anthropic-key deploy.sh`, the `@anthropic-key` placeholder is resolved inline at subprocess spawn time, injected into child env, never echoed

**Mode C — bw (Bitwarden):**
- Same pattern as op. `hangar secret set x --ref bw://item-id/field`
- Shells to `bw get password <item-id>` with `BW_SESSION` env var (user must unlock first: `hangar bw unlock`)

**Mode D — ssh_agent:**
- `hangar secret set deploy-key --ref ssh-agent://SHA256:abcd...`
- Used for SSH commands — CLI adds key to `SSH_AUTH_SOCK` env, spawns child, removes after
- For `hangar run ssh-*` commands, this is the default flow

**UI (dashboard Spec 1 already has):**
- Project detail → "Secrets" tab (Phase 3 extension — can be added without Spec 4)
- For each secret: label, kind-badge, masked reference-or-value, "Rotate" / "Remove" actions
- CLI commands already cover this — dashboard UI is nice-to-have follow-up

### 4.6 Claude skill

Single markdown file installed to `~/.claude/skills/hangar/SKILL.md`. Per HANGAR.md §8 exact text:

```markdown
---
name: hangar
description: >
  Use this skill whenever the user references any of their projects, says
  "what am I working on", "continue", "switch to <project>", "log this",
  "ship it", "brief me", "what did I decide about X", or uses pronouns
  referring to "this project" / "the project". Also: on every new session,
  call hangar.active() first to load context.
---

[full skill body per HANGAR.md §8]
```

Auto-install:
- `hangar skill install` copies file into `~/.claude/skills/hangar/SKILL.md`
- `hangar skill update` re-syncs
- If Claude CLI isn't installed (no `~/.claude/` dir), fallback to stdout instructions

### 4.7 MCP tools (v1 surface — per HANGAR.md §7)

**Read (10 tools):**
`hangar.ping`, `hangar.active`, `hangar.list`, `hangar.get`, `hangar.brief`, `hangar.health`, `hangar.search`, `hangar.recent_sessions`, `hangar.decisions`, `hangar.prompts.search`

**Write (9 tools):**
`hangar.switch`, `hangar.log_session`, `hangar.update_context`, `hangar.decision`, `hangar.idea`, `hangar.ship`, `hangar.note_append`, `hangar.link_add`, `hangar.status`

**Execute (3 tools):**
`hangar.run` (saved command), `hangar.claude_md` (generate CLAUDE.md), `hangar.handover` (onboarding brief)

**Deferred to Spec 3.1 follow-up:**
- MCP hub-relay (tunneling sub-MCPs from active project's integrations)
- `hangar.prompts.run` (prompt runner — needs AI provider connectors from Spec 5)
- `hangar.specs.*` (needs knowledge vault from Spec 5)

## 5. Phase breakdown

| # | Phase | Deliverable |
|---|---|---|
| 0 | Rust workspace + CI | `cargo` project, `hangar --version`, GitHub Actions matrix (macOS/Linux/Windows) |
| 1 | Device-code pairing | `hangar pair` + backend `/cli/pair/*` endpoints + OS-keychain token storage |
| 2 | Local SQLite cache + initial sync | `hangar sync` pulls projects, CLI reads local |
| 3 | Daemon autostart | launchd plist / systemd user unit / Task Scheduler — `hangar daemon start/stop/status` |
| 4 | HTTP MCP server stub + bearer auth | `hangar mcp-token` command, bearer handshake verified with `mcp-inspector` |
| 5 | MCP read tools (10) | `hangar.ping`, `active`, `list`, `get`, `brief`, `search`, `recent_sessions`, `decisions`, `health`, `prompts.search` |
| 6 | MCP write tools (9) | `switch`, `log_session`, `update_context`, `decision`, `idea`, `ship`, `note_append`, `link_add`, `status` |
| 7 | Secret resolver | `hangar secret set/list/rotate`, `op`/`bw`/`ssh-agent`/`inline_encrypted` kinds |
| 8 | `hangar.run` + CLAUDE.md + handover | execute tool + generators |
| 9 | Claude skill installer | `hangar skill install/update`, skill body matches HANGAR.md §8 |
| 10 | E2E integration + cross-compile | single Playwright-style test: Claude Code → MCP → Hangar DB round-trip. Binaries for 3 platforms in release artifacts |

Each phase keeps the binary shippable. By P5, user can `hangar get hangar` in terminal. By P9, Claude Code auto-loads context.

## 6. Out of scope

- **Windows service installer beyond scheduled-task** — scheduled-task works; proper SCM registration is Spec 3.1
- **MCP hub-relay** (HANGAR.md §3.11) — depends on 3rd-party MCP servers being installed; defer
- **Agent-run-monitoring dashboard** ("Claude still working on X, last output 2m ago") — UI work on dashboard that depends on WS heartbeat from daemon; Spec 3.1
- **Prompt-runner + specs/snippets** — depend on Spec 5 knowledge vault
- **Stripe/Vercel/etc. MCP-relay** — sub-MCPs

## 7. Backwards compatibility

No schema breakage. All changes are additive:
- `cli_devices` table already present (Spec 1); populate now
- `project_secret_refs` table was spec'd in HANGAR.md §4.2 but deferred in Spec 1 — add in Spec 3 migration `0003_secrets.py`
- New endpoints under `/api/v1/cli/*` and `/api/v1/projects/:slug/secrets/*`
- Existing web UI unchanged

## 8. Security review

- **MCP bearer token on 127.0.0.1 only** — daemon refuses binds to 0.0.0.0
- **Device token** in OS keychain, never in plaintext on disk
- **Secret values** never logged, never cached, clipboard auto-cleared 45s
- **Daemon logs** redact `op://` / `bw://` references contain no secret values
- **Client-cert pinning** for hangar.dev: `reqwest` uses `rustls` with embedded DigiCert root — deferred until prod TLS is live, for now trust system roots
- **Outbox files** (queued writes when offline) never contain raw secrets — only their references

## 9. Rollout

1. Phase 0-3: internal dev-only, local binary for lenny
2. Phase 4-6: macOS-only first, test via Claude Code against staging backend
3. Phase 7-9: all platforms via GitHub Actions matrix
4. Phase 10: `curl -LsSf hangar.dev/install.sh | sh` landing page, `brew` tap (`lennystepn/tap/hangar`), Scoop bucket

**End of Spec 3 design.**
