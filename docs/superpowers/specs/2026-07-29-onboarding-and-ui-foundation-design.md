# Onboarding & UI Foundation — Design

Date: 2026-07-29
Status: approved, ready for implementation
Scope: onboarding rebuild (stream A) + UI/UX foundation (stream U)

Written in English to match the rest of `docs/` and the codebase. Discussion
happened in German; nothing is lost, the decisions are all here.

---

## 1. Why

Two problems, measured rather than guessed.

**Onboarding delivers no value before it ends.** The current wizard
(`frontend/src/pages/Welcome.vue`, 608 lines) runs three steps: create an
*empty* project, choose among *six* editor tabs, land in an *empty* console.
Every aha-moment Vibecell has — portfolio appears without typing, Claude
already knows where you left off, decay is visible, sessions log themselves —
happens after the wizard is over, where no new user is watching. Step 2 also
asks for a decision ("which editor tab?") that a new user is not yet equipped
to make.

**The design system exists but is not enforced.** `assets/tokens.css` is well
built and ships three themes (default, `terminal-green`, `paper`). Yet an audit
of 98 `.vue` files (16,580 lines) found:

| Count | Finding |
|---|---|
| 267 | hardcoded colour literals (`rgba(...)` / hex) inside `style="…"` across 29 files |
| 979 | lines in `AnonLanding.vue` — the most important page is the least maintainable, 138 of the literals live there |
| 16 | equally-weighted widgets on the project console (`widget-registry.ts`) |
| 0 | Card/Panel primitives — 14 UI primitives exist, but the app's most common element is a bare `.glass` CSS class each site re-assembles |

The 267 literals are not cosmetic. `style="background:rgba(20,33,50,0.5)"` in
`Welcome.vue` renders a dark navy box on light paper: **the `paper` and
`terminal-green` themes are shipped broken.**

## 2. Goals

1. Signup → full, enriched portfolio in under two minutes, with no typing.
2. MCP installation configures *every* MCP client on the machine from one user
   action.
3. The web UI shows what the agent is doing, live, while it happens.
4. All three themes render correctly on every screen, and stay that way.

## 3. Non-goals

- Reversing the funnel so pairing replaces signup (evaluated as approach C,
  deferred: it is approach A with a different entry point and becomes a
  one-day landing change once A ships).
- New product features (AI cost attribution, knowledge vault, feedback inbox,
  domain inventory). Tracked separately as stream E.
- iOS app, browser extension.

## 4. Decisions

### 4.1 Onboarding logic lives in the MCP, not in a pasted prompt

Today the routine is frozen text in `frontend/src/lib/installPrompt.ts`. A user
who pasted it once never receives an improvement.

A new MCP tool `vibecell_onboard()` returns the routine as instructions to the
agent. The pasted prompt shrinks to two lines ("connect to Vibecell, then call
`vibecell_onboard` and follow it"). The routine becomes server-side and
editable without any user re-pasting.

### 4.2 One line wires up every MCP client

`frontend/public/install.sh` and `install.ps1` already exist, but only download
the Rust binary and then print *"next: run `hangar pair`"*. They touch no MCP
configuration. That is the gap.

The onboarding screen shows one OS-appropriate line:

```
curl -LsSf https://vibecell.dev/i/AB12CD | sh      # macOS / Linux
irm https://vibecell.dev/i/AB12CD | iex            # Windows
```

`AB12CD` is a short-lived single-use pairing code bound to the account. The
script installs the binary as today, then calls a **new** CLI subcommand
`hangar setup --code AB12CD`, which:

1. Exchanges the code for a device token — no OAuth click, no browser round
   trip. Reuses the existing device-code machinery in
   `backend/app/api/v1/cli.py` (`/pair/start`, `/pair/complete`, `/devices`).
2. Detects and configures every installed MCP client:

   | Client | Target |
   |---|---|
   | Claude Code | `claude mcp add` / `~/.claude.json` |
   | Claude Desktop | `claude_desktop_config.json` (per-OS path) |
   | Cursor | `~/.cursor/mcp.json` |
   | Windsurf | `~/.codeium/windsurf/mcp_config.json` |
   | Zed | `settings.json` → `context_servers` |

   Writes are additive and idempotent: existing servers are preserved, an
   existing `vibecell` entry is updated in place, malformed config aborts that
   client and continues with the rest.
3. Installs the Claude skill (the CLI already has a `Skill` subcommand).
4. Reports each step to the backend so the web page's live log fills in real
   time: `✓ Claude Code · ✓ Cursor · ○ Zed not found`.

**Honest limit, stated for the record:** a web page cannot install anything on
a machine by itself. Something has to run locally. The minimum possible user
action is one terminal line or one deep-link click. There is no zero-action
path that is not malware. The deep-link route (`claude://add-connector?url=`,
`cursor://anysphere.cursor-deeplink/mcp/install?…`) therefore stays as the
no-terminal option for single-app users; the one-liner is for everyone with
more than one editor.

### 4.3 Pairing-code security

- Valid for 10 minutes, single-use.
- Scope is *device pairing only* — no account access, no project reads.
- The resulting device token is revocable from Settings via the existing
  `DELETE /api/v1/cli/devices/{id}`.
- The onboarding screen silently reissues the code over the open SSE
  connection before it expires, so the line on screen is never dead.

Rationale: the code lands in shell history. Single-use is what protects it —
by the time anyone reads it there it has been spent, and what it produced is
independently revocable. The time window only bounds shoulder-surfing, so it
is sized for a human copying a line into a terminal rather than for a
threat model it does not actually address. 60 seconds was considered and
rejected: it expires mid-paste for anyone who has to open a terminal first.

### 4.4 Live channel reuses SSE, not a new transport

`backend/app/api/v1/events.py` already streams per-project events consumed by
`composables/useProjectLive.ts` via `EventSource`. The wizard, by contrast,
polls `connections.refresh()` every 3 seconds and learns nothing but "the list
got longer".

Add a **user-scoped** stream `GET /api/v1/onboarding/stream` of the same
construction, carrying:

| Event | Payload |
|---|---|
| `paired` | `{client}` |
| `client.configured` | `{client, ok, reason?}` |
| `scan.started` | `{repo_count}` |
| `project.created` | `{slug, name}` |
| `project.enriched` | `{slug, pitch, stack}` |
| `done` | `{project_count}` |

Both `hangar setup` and `vibecell_onboard` publish to it.

### 4.5 Enrichment runs on the user's machine

Claude reads `README`, `package.json`, `pyproject.toml` and commit history
locally. Cost sits with the user's own subscription, no GitHub scope is needed,
no AI bill lands on Vibecell. Only the no-editor fallback path runs server-side
via the existing `github_repos.py`, on Vibecell's budget — which is precisely
why it is the second path and not the first.

### 4.6 Foundation before showcase

U1 and U2 ship before the new onboarding screen. Building the product's
flagship screen on top of 267 hardcoded colour literals means building it
twice. Decided explicitly by the user after being shown the alternative.

## 5. Architecture

```
Browser (onboarding screen)                Backend                     User machine
──────────────────────────                ─────────                   ──────────────
  request pairing code   ──────────────►  POST /api/v1/onboarding/code
                                            (60s, single-use)
  show OS-specific one-liner
  open EventSource       ──────────────►  GET /api/v1/onboarding/stream
                                                    ▲
  user pastes line ─────────────────────────────────┼──────────────►  install.sh
                                                    │                 hangar setup --code
                                            POST /api/v1/onboarding/events
                                                    │                 ├ exchange code → token
  live log fills  ◄───────────────────────────────  ┤                 ├ detect + write MCP configs
                                                    │                 └ install skill
                                                    │
  portfolio builds  ◄─────────────────────────────  ┤   MCP: vibecell_onboard()
                                                    └───────────────  agent scans repos,
  final screen: triage                                                creates + enriches projects
```

## 6. Work breakdown

Twelve sessions. Each is independently shippable and independently deployable.

### Foundation

| # | Session | Depends on |
|---|---|---|
| U1 | Theme integrity: 267 literals → tokens, plus a CI guard that fails the build on new ones | — |
| U2 | Card/Panel primitive + type scale; all 16 widgets and every page moved onto it | U1 |

### Stream A — onboarding

| # | Session | Depends on |
|---|---|---|
| A1 | User-scoped onboarding SSE stream + frontend store | — |
| A2 | One-time pairing codes: `POST /onboarding/code`, `GET /i/<code>` serving a token-stamped install script, silent reissue before expiry | A1 |
| A3 | `hangar setup --code`: MCP client detection, idempotent config writes, skill install, progress reporting | A1, A2 |
| A4 | MCP tool `vibecell_onboard`: scan/create/enrich routine + progress events | A1 |
| A5 | Onboarding screen: single detected path, deep-link with failure detection, live log | U1, U2, A1, A3 |
| A6 | Completion screen: portfolio with triage instead of an empty console | A4, U2 |
| A7 | No-editor fallback: GitHub import with server-side enrichment | A4 |
| A8 | Empty states app-wide: "let Claude fill this" instead of "nothing here yet" | U2, A4 |

### Stream U — remaining UI/UX

| # | Session | Depends on |
|---|---|---|
| U3 | Project console ordered by urgency: a "now" zone above everything, the rest progressively disclosed | U2 |
| U4 | Visual signature: one recurring signature element, motion as language, `AnonLanding.vue` decomposed | U1, U2 |

### Deep-link failure detection (detail for A5)

A browser cannot see which applications are installed. What A5 actually does:
detect the OS, propose the most likely path, fire the deep link, and watch for
`visibilitychange`. No focus loss within ~1.5s means no protocol handler is
registered → silently fall through to the one-liner. The six editor tabs
collapse into a quiet "different editor" link.

## 7. Testing

- **U1** — CI guard is the test: a grep-based check in the existing GitHub
  Actions workflow fails on any new `style="…"` containing a colour literal.
  Plus a Playwright screenshot per theme on three representative pages.
- **U2** — component tests for the Card primitive; visual diff on the console.
- **A1** — the stream is testable in isolation: publish events, assert the
  client receives them in order, assert teardown on disconnect.
- **A2** — expiry, single-use, and scope are three separate unit tests.
  A code must not be redeemable twice, after 60s, or for anything but pairing.
- **A3** — the config writers get fixture-based tests per client: empty config,
  existing config with other servers, existing `vibecell` entry, malformed
  JSON. Idempotency is asserted by running twice and diffing.
- **A5–A8** — Playwright end-to-end against a stubbed event stream.

## 8. Risks

| Risk | Mitigation |
|---|---|
| MCP client config formats change upstream | Writers are isolated per client with fixture tests; one breaking does not break the others |
| `curl \| sh` is refused by security-conscious users | The deep-link path and the manual per-editor instructions both remain reachable |
| Agent-side enrichment quality varies by model | The routine is server-side (4.1) and can be tightened without user action |
| Empty repo / no repos found | A7 fallback and A8 empty states cover it; `done` fires with `project_count: 0` and the screen adapts |

## 9. Out of scope, tracked separately

Stream E (new features) remains undesigned: AI cost attribution per project,
knowledge vault, feedback inbox, domain inventory, weekly builder review, MCP
hub relay, launch tracker. Each needs its own design pass before implementation.
