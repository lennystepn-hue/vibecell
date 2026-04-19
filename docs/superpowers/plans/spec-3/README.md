# Spec 3 Implementation Plan — Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Implement phase-by-phase with full staging verification after each.

**Goal:** Ship Hangar's CLI + daemon + MCP server + Claude skill. Turn Hangar from "web dashboard" into "the OS Claude Code breathes through."

**Spec:** [docs/superpowers/specs/2026-04-19-spec-3-cli-mcp-skill-design.md](../../specs/2026-04-19-spec-3-cli-mcp-skill-design.md)

**Architecture:** Rust static binary (`hangar`) that does double-duty as CLI and daemon. Daemon hosts an HTTP MCP server at `127.0.0.1:7421` that Claude Code (and any MCP client) connects to. Local SQLite cache for sub-ms reads, WebSocket sync to Hangar backend at `hangar.dev` (currently `89.167.111.89:8080`). Secrets resolve via 1Password / Bitwarden / ssh-agent / inline-encrypted — references stored in Hangar DB, values never traverse cloud. Device-code pairing flow; token stored in OS keychain.

**Tech Stack:** Rust 1.83+, `tokio`, `axum`, `rmcp` (MCP SDK), `reqwest`, `rusqlite`, `tokio-rusqlite`, `keyring`, `serde`, `clap` 4, `tracing`, `anyhow` + `thiserror`. Cross-compile via `cross` + GitHub Actions matrix (macOS universal / Linux x86_64 / Windows x86_64).

---

## Phase order

| # | Phase | File |
|---|---|---|
| 0 | Rust Workspace + CI | [phase-00-rust-workspace.md](phase-00-rust-workspace.md) |
| 1 | Device-code Pairing | phase-01-pairing.md (TBD, writes before execution) |
| 2 | Local Cache + Sync | phase-02-cache-sync.md |
| 3 | Daemon Autostart | phase-03-daemon.md |
| 4 | HTTP MCP Server | phase-04-mcp-server.md |
| 5 | MCP Read Tools | phase-05-mcp-read.md |
| 6 | MCP Write Tools | phase-06-mcp-write.md |
| 7 | Secret Resolver | phase-07-secrets.md |
| 8 | `hangar.run` + Generators | phase-08-run-generators.md |
| 9 | Claude Skill Installer | phase-09-skill.md |
| 10 | E2E + Cross-compile Release | phase-10-release.md |

Phase plan files are written JIT (just-in-time) — when Phase N starts, Phase N+1 plan is written so lessons from execution inform the next phase.

## Working rules (all phases)

- **Cross-platform from Phase 0.** CI matrix runs `cargo build --release` on macOS/Linux/Windows. If a platform breaks, fix before phase completes.
- **Static binary.** No dynamic deps on user's machine (except `op` / `bw` CLIs which are user-installed by choice).
- **One task = one commit.** Commit format: `feat(cli): ...` / `chore(cli): ...` / `test(cli): ...`.
- **Real-infra verification.** Each phase that touches HTTP hits staging backend `89.167.111.89:8000`. Keychain/filesystem tests use tempdirs.
- **Pre-existing backend is live.** Don't break it — add new endpoints under `/api/v1/cli/*` and new columns only via migrations.
- **Every commit keeps both `cargo build --release` and `cargo test` green** on Linux-x86_64 at minimum. Cross-platform verification on GitHub Actions.

## Monorepo layout after Phase 0

```
hangar/
├── backend/                 (existing — Spec 1)
├── frontend/                (existing — Spec 1)
├── ops/                     (existing — Spec 1)
├── cli/                     (NEW — Spec 3)
│   ├── Cargo.toml
│   ├── Cargo.lock
│   ├── src/
│   │   ├── main.rs          CLI entry: clap dispatch
│   │   ├── lib.rs           library surface for tests
│   │   ├── cmd/             one module per CLI subcommand
│   │   │   ├── mod.rs
│   │   │   ├── pair.rs
│   │   │   ├── sync.rs
│   │   │   ├── daemon.rs
│   │   │   ├── mcp.rs
│   │   │   ├── secret.rs
│   │   │   └── skill.rs
│   │   ├── daemon/          daemon process (`hangar daemon start` exec)
│   │   │   ├── mod.rs
│   │   │   └── mcp_server.rs
│   │   ├── cache/           SQLite layer
│   │   │   ├── mod.rs
│   │   │   └── schema.rs
│   │   ├── cloud/           hangar.dev REST + WebSocket client
│   │   │   └── mod.rs
│   │   ├── keychain.rs      cross-platform keyring wrapper
│   │   ├── config.rs        ~/.hangar/config.toml parser
│   │   └── resolver.rs      secret resolvers (op/bw/ssh/inline)
│   └── tests/
│       └── integration/
├── .github/workflows/cli.yml  (NEW — Rust CI matrix)
└── docs/superpowers/
    ├── specs/2026-04-19-spec-3-cli-mcp-skill-design.md
    └── plans/spec-3/
        └── phase-00-...md (onwards)
```

## Success criteria for Spec 3

1. `curl -LsSf https://hangar.dev/install.sh | sh` installs `hangar` on macOS / Linux
2. `hangar pair` runs the full device-code flow, stores token in keychain
3. `hangar daemon start` launches service via launchd / systemd / Task Scheduler
4. Claude Code's MCP config pointed at `http://127.0.0.1:7421/mcp` with bearer-token discovers 22 tools
5. Opening any project's local repo in Claude Code triggers `hangar.active()` via the skill, context loads
6. Saying "log this, done" triggers `hangar.log_session(...)` — dashboard shows the new session within 1s
7. `hangar secret set stripe --ref op://Private/Stripe/api-key` — CLI resolves via `op read` when `hangar run deploy-stripe-webhook` executes; stripe key never logged
8. Offline (disconnect wifi): reads still work from cache, writes queue; reconnect replays
9. `cargo test --workspace` + `cargo clippy` both green in CI on 3 platforms
