# HANGAR

**The operating system for vibecoders.**

A single source of truth for every project a solo builder is shipping — context, costs, customers, domains, distribution, decisions — with Claude Code plugged straight in via a local MCP server.

This document is the full specification. Read it top to bottom before touching code.

---

## 1. Product definition

### One-sentence

Hangar is a web SaaS + thin local CLI agent that holds the live state of every project you're building and exposes it to Claude Code as first-class tools.

### Problem

A vibecoder runs 10–50 projects in parallel. The operational load — "which server runs this, what was I doing, what did the user want, is anything on fire, which API is burning my money, when does that domain expire, what did I decide three months ago" — is the bottleneck, not the building. Existing tools (Notion, per-repo `CLAUDE.md`, spreadsheets, memory) fail at scale and none of them integrate with Claude Code.

### Solution

One surface that holds everything. One keystroke to switch projects. Claude Code instantly knows stack, infra, last session, next step, open questions. AI costs attributed per project across providers. Public project pages built in. Ship loop as a first-class primitive. Local-first via the CLI, synced to the cloud, MIT core.

### Target user

A solo builder who:

- Runs 10+ projects at various life stages (idea, building, live, revenue, dormant, archived).
- Ships with Claude Code or Cursor as primary coding partner.
- Self-hosts or uses Vercel / Supabase / Hetzner / Fly across projects.
- Spends measurably on AI APIs (Anthropic, OpenAI, Groq, Replicate, etc.).
- Distributes primarily via X, Product Hunt, and Hacker News.
- Owns multiple domains, has had at least one viral moment, ships multiple times per week.

Secondary: small agencies and duo teams with the same workflow.

Not the target: enterprise PM use cases, traditional agile teams, non-technical users.

---

## 2. Architecture

### Three physical pieces

```
        hangar.dev                 ~/.hangar/hangar              Claude Code
   ┌──────────────────┐         ┌──────────────────┐         ┌─────────────┐
   │  Web dashboard   │◄───────►│   CLI + daemon   │◄───────►│   Hangar    │
   │  (Vue SPA)       │  sync   │  (Rust, static)  │   MCP   │   skill     │
   │                  │         │                  │         │             │
   │  FastAPI API     │         │  - local cache   │         └─────────────┘
   │  Postgres        │         │  - MCP server    │
   │  Hetzner         │         │  - filesystem    │
   └──────────────────┘         │  - terminal ops  │
                                └──────────────────┘
```

- **hangar.dev** — the SaaS. Dashboard, projects, costs, domains, ideas, public pages, billing. Vue 3 SPA + FastAPI + Postgres on Hetzner.
- **`hangar` CLI** — static Rust binary installed via `brew install hangar` or `curl | sh`. Runs as background daemon on `127.0.0.1:7421`. Hosts the MCP server, maintains a local SQLite cache for offline + speed, does all filesystem and terminal work. Pairs with your account via device-code flow.
- **Hangar Claude skill** — the Claude Code integration layer. Installed into the user's skill directory by the CLI. Handles session-start context loading and session-end logging automatically.

### Data flow

- CLI daemon keeps a local SQLite cache. All reads go local-first (sub-millisecond).
- Writes go to cloud API via WebSocket (live) with REST fallback (bulk / offline catchup).
- Cloud is the source of truth; CLI is a cache. Conflict resolution: last-write-wins with server timestamp.
- MCP calls from Claude Code hit the CLI daemon directly (never the cloud) — zero latency, works offline.
- Background worker (cloud-side) runs health checks, integration polls, AI cost aggregation.

### Active project is global state

At any moment exactly one project is "active." This is the mode Claude Code and the CLI operate in. Switching the active project is the only context action the user cares about. All MCP reads default to the active project unless a slug is explicitly passed.

---

## 3. Feature set

Organized by the domain of pain each feature removes. Every feature in this list is in scope. Features outside this list are explicitly out of scope.

### 3.1 Project registry

The canonical record for every project:

- **Identity**: slug, display name, emoji, color accent, one-line pitch, status (`idea | building | live | paused | shipped | archived | dead`), tags.
- **Repos**: one or more Git repos per project (for monorepos and split web/api/worker setups). Each has URL, default branch, local path, primary language, license.
- **Environments**: local, preview, staging, prod — each with URL, env vars template path, DB alias.
- **Stack**: frontend, backend, DB, deploy target, key libraries (referenced against a shared `stack_items` catalog so "Supabase" is one entity queryable across projects).
- **Infra**: server alias (points to `~/.ssh/config` entry, never the key itself), primary domain + all domains, DNS provider, DB host, CDN, object storage bucket.
- **Links**: live URL, staging URL, docs, X post, Product Hunt, Discord, Stripe dashboard, analytics dashboard, monitoring dashboard, etc.
- **Business**: monetization model, MRR (auto-synced if Stripe connected), affiliate programs, pricing page URL, legal entity (Wyoming LLC, GmbH, personal).
- **Lifecycle events** (auto-captured where possible): first commit, first deploy, first user, first paying customer, first $100 month, first $1k month, PH launch, HN front page, viral X moment.

### 3.2 Context and ship loop

The atomic unit of a vibecoder's week is a ship, not a session.

- **Current context** per project: current focus (one sentence), next step (concrete action), what the user wants, open questions, known issues, blocked-by.
- **Session log** — auto-written by the Claude skill at session end: summary, files touched, commits, inferred next step.
- **Decision log** — append-only, ADR-lite: title, context, decision, consequences, "reconsider if".
- **Idea inbox** — global and per-project. Quick capture, triage to project or discard, convertible to a task or spec.
- **Ship button** — one click triggers: generate changelog entry from commits + sessions since last ship, draft 3 announce-tweet variants, update public page, bump version tag, log a `ship` event.
- **Launch tracker** — every launch event (PH, HN, X thread, Reddit, newsletter) with traction metrics (upvotes, visitors, signups in the next 24h).
- **Viral moment capture** — paste a tweet URL, Hangar pulls impressions + replies + screenshots into that project's timeline.

### 3.3 AI cost and stack intelligence

The feature that sells the product. No competitor has this.

- **Unified AI spend dashboard** across Anthropic, OpenAI, Groq, Replicate, xAI, Gemini, Perplexity, OpenRouter, Together, Fireworks. API keys stored encrypted in the OS keychain (CLI) or with user-derived key (cloud); never plaintext in DB.
- **Per-project attribution** — preferred method: project-specific API keys (cleanest split). Fallback: request tagging. Fallback to fallback: user-assigned monthly allocation.
- **Burn-rate alerts** — "Butlr Anthropic spend is 4x last 7-day average."
- **Credit balance tracking** — remaining credits per provider, days-of-runway at current rate.
- **Model usage mix** per project — which model for which workload, costs, token counts.
- **Stack catalog** — every library, service, and model a project uses is tagged against shared entities. Queryable: "Which of my projects use Supabase / shadcn / Resend?"
- **Stack diff** between any two projects.
- **Starter generator** — spin up a new project inheriting the stack + infra pattern of an existing one. Scaffolds `package.json`, env templates, deploy config.

### 3.4 Portfolio health

Background worker, cloud-side, polls every 5–15 minutes:

- Git staleness (days since last commit, days since last push).
- Live URL uptime (HEAD requests).
- SSL certificate days-remaining.
- Domain days-to-expiry.
- GitHub: open issues, open PRs, stars, Dependabot alerts.
- Deploy status (via Vercel / Netlify / Railway / Fly APIs).
- DNS records health: SPF, DKIM, DMARC presence and validity.
- Heartbeat URLs for cron jobs (Cron-Hub pattern, built in).
- **Needs-attention triage queue** — prioritized list surfaced on the dashboard.
- **Momentum score** per project — derived from commit frequency, session count, deploys, revenue movement over last 30 days.

### 3.5 Revenue and P&L

- **Stripe / Lemon Squeezy / Paddle / RevenueCat connections** per project.
- MRR, churn, LTV, new/lost customers this week.
- **P&L per project**: MRR − (AI spend + infra spend + attributed SaaS subscriptions) = actual margin.
- **Portfolio P&L** — rolled up across all projects.
- **"Acquire or kill" signal** — flag projects losing money three months running; flag projects with 3x margin to double down on.
- **Subscription tracker** — every SaaS tool you pay for, attributed to one or more projects, renewal calendar.

### 3.6 Distribution and social

- **X OAuth integration** — surface every post tagged to each project, track impressions + replies + clicks.
- **Draft-and-schedule** — from any project page, draft announce/progress tweets, schedule or send.
- **Public project pages** at `hangar.dev/<workspace>/<slug>` — stack, status, live URL, changelog, lifecycle events. SEO-ready, shareable. Custom domain on Studio tier.
- **Portfolio page** at `hangar.dev/<workspace>` — all public projects, unified. Doubles as personal site.
- **Launch calendar** — PH queue, HN timing, newsletter sends, scheduled posts — one timeline.
- **GEO / AI discoverability tracking** — does Claude / ChatGPT / Perplexity find this project when asked? Tracked per project over time. (Wraps Lenny's agentcheck.site concept natively.)

### 3.7 Customer and feedback loop

- **Feedback inbox** — each project gets an email forwarding address (`<slug>@inbox.hangar.dev`). Incoming items triaged as bug / feature / praise / complaint / other.
- **X mentions** for the project's URL or tagged handle feed into the same inbox.
- **Discord / Telegram webhooks** optional.
- **Beta cohort management** — who's in which beta, invited when, active or silent.
- **Voice-of-customer digest** — weekly AI-generated per-project summary of feedback.
- **Testimonials vault** — capture praise, tag with permission status, reuse on public page.

### 3.8 Knowledge vault

Everything a vibecoder otherwise loses in scattered files.

- **Prompt library** — versioned, taggable, runnable (test against Anthropic / OpenAI / Groq in-app). Linkable from sessions and decisions.
- **Spec library** — markdown specs for past and current projects, searchable, cloneable as new-project starters.
- **Skill library** — your Claude skills. Local per workspace, optionally public (proto-marketplace).
- **Template library** — project starters (package.json + infra + envs) blessed by you.
- **Snippet library** — env templates, docker-compose patterns, SQL migrations, regex, shell one-liners.
- **Global FTS search** across every text field in every table.

### 3.9 Domain and asset inventory

- **Every domain** imported via Cloudflare / Namecheap / Porkbun APIs.
- Status: live / parked / for-sale / dormant / redirect target.
- Expiry calendar, iCal export.
- Rough estimated value.
- Suggested retirements / consolidations.
- **Assets per project** — favicon, OG image, logo, screenshots, brand colors — versioned, hosted, URL-addressable.

### 3.10 Legal and compliance (EU-critical)

- **Privacy policy / terms / imprint / cookie policy** URLs tracked per project, with annual review reminders.
- **GDPR records** — data categories processed, subprocessors, lawful basis, DPA links.
- **VAT registration** status per country.
- **Legal entities** — which entity owns which project, for invoicing and tax.
- **Contract vault** — Stripe accounts, bank accounts, tax IDs as references (no numbers stored).

### 3.11 Claude Code and agent integration

The technical moat. See §5, §7, §8 for detail.

- **MCP server** on `127.0.0.1:7421` hosted by the CLI daemon.
- **Active project is global state** — every MCP call respects it.
- **MCP hub relay** — when active project = Butlr, Hangar transparently relays calls to Butlr's configured sub-MCPs (Stripe MCP, Supabase MCP, Vercel MCP, custom). Claude Code sees one tool list that changes per active project.
- **`CLAUDE.md` generator** — synthesize a complete `CLAUDE.md` for the active project's repo from its Hangar record. On demand; never auto-commits.
- **Skill auto-install** — CLI installs the Hangar skill into the user's Claude skills directory and keeps it updated.
- **Session hooks** — skill calls `log_session` automatically on session end.
- **Agent run monitoring** — long-running Claude Code sessions visible in the Hangar dashboard: "still working on X, last output 2m ago."
- **Handover brief generator** — produces a full onboarding document for a new human or AI collaborator.
- **Multi-client** — works with Claude Code, Claude Desktop, Cursor, Zed, any MCP-capable client.

### 3.12 Builder identity (the layer above projects)

- **You, the builder** — GitHub handle, X handle, email, owned domains, legal entities.
- **Portfolio momentum** — ship count, commit streaks, launches, MRR growth across all projects.
- **Weekly builder review** — every Sunday, AI-generated: what you shipped, what moved, what's stuck, what to kill, top 3 priorities next week. Email + in-app.
- **"Now" page** — single public page aggregating everything you're building live. Optional.

### 3.13 Capture and multi-device

- **Web dashboard** — desktop and tablet responsive. Keyboard-first: `Cmd+K` palette, global switch shortcut, all actions keyboard-reachable.
- **CLI** — offline-capable reads and writes, syncs on reconnect.
- **iOS companion app** — read-only dashboard, voice idea capture (transcribed to idea inbox), push notifications for alerts. Shortcuts widget.
- **Browser extension** — one-click capture of URLs, competitor pages, tweets, screenshots into the right project.
- **Email-to-inbox** — every project has `<slug>@inbox.hangar.dev` for capturing feedback, invoices, notes.

### 3.14 Security and privacy

- **No plaintext secrets in the cloud DB, ever.** Only references.
- **Integration API keys** encrypted with a key derived from the user's master password (or passkey). Server holds only ciphertext for sensitive fields.
- **CLI-local secrets** (SSH, 1Password references) never leave the machine.
- **Device-code pairing** for CLI — no long-lived cloud API key floating around.
- **Audit log** — every write, by whom (UI, MCP, worker), reversible within 30 days.
- **EU hosting by default** — Hetzner Germany / Finland.
- **Self-host option** — Hangar Core is MIT-licensed, runnable via Docker Compose on your own infra. Paid cloud is the convenience layer.
- **No third-party trackers** on public pages. Plausible self-hosted for first-party analytics.

### 3.15 Explicitly out of scope

- Gantt charts, burndown charts, sprint planning.
- In-app chat or DMs between users.
- Generic note-taking (Hangar is not Notion — notes exist as per-project markdown, nothing more).
- Calendar / time-blocking.
- Custom user-buildable dashboards.
- Enterprise SSO / SAML / SCIM.
- Multi-tenant at workspace level beyond simple invite-viewer (no complex roles).

---

## 4. Data model

All tables in cloud Postgres. CLI maintains a mirrored SQLite cache for read speed.

IDs are ULIDs. Timestamps are ISO 8601 strings in UTC. JSON columns are used where schema is open-ended.

### 4.1 Account and workspace

```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  handle TEXT UNIQUE,
  passkey_credentials JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE workspaces (
  id TEXT PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  owner_id TEXT NOT NULL REFERENCES users(id),
  plan TEXT NOT NULL DEFAULT 'free',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE workspace_members (
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'owner',
  PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE cli_devices (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT,
  paired_at TIMESTAMPTZ NOT NULL,
  last_seen_at TIMESTAMPTZ,
  token_hash TEXT NOT NULL
);

CREATE TABLE audit_log (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  actor TEXT NOT NULL,          -- 'ui:<user_id>' | 'mcp:<device_id>' | 'worker'
  op TEXT NOT NULL,             -- 'create' | 'update' | 'delete'
  entity TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  diff JSONB
);
```

### 4.2 Projects

```sql
CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  emoji TEXT,
  color TEXT,
  pitch TEXT,
  status TEXT NOT NULL DEFAULT 'building',
  legal_entity_id TEXT REFERENCES legal_entities(id),
  is_public INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  archived_at TIMESTAMPTZ,
  UNIQUE (workspace_id, slug)
);

CREATE TABLE active_project (
  workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  set_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE project_repos (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  role TEXT,                    -- 'web' | 'api' | 'worker' | 'monorepo' | free
  git_url TEXT,
  default_branch TEXT DEFAULT 'main',
  local_path TEXT,
  primary_lang TEXT,
  license TEXT
);

CREATE TABLE project_environments (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,           -- 'local' | 'preview' | 'staging' | 'prod'
  url TEXT,
  env_template_path TEXT,
  db_alias TEXT
);

CREATE TABLE project_infra (
  project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
  server_alias TEXT,
  domain_primary TEXT,
  domains JSONB DEFAULT '[]'::jsonb,
  dns_provider TEXT,
  db_host TEXT,
  cdn TEXT,
  object_storage TEXT
);

CREATE TABLE project_context (
  project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
  current_focus TEXT,
  next_step TEXT,
  user_wants TEXT,
  open_questions JSONB DEFAULT '[]'::jsonb,
  known_issues JSONB DEFAULT '[]'::jsonb,
  blocked_by TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE project_links (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind TEXT,                    -- 'live' | 'staging' | 'docs' | 'x' | 'ph' | 'stripe' | 'analytics' | ...
  label TEXT,
  url TEXT NOT NULL
);

CREATE TABLE project_secret_refs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  label TEXT NOT NULL,
  kind TEXT NOT NULL,           -- 'ssh_config' | 'onepassword' | 'bitwarden' | 'env_path' | 'keychain'
  reference TEXT NOT NULL       -- e.g. 'op://Private/Butlr/STRIPE_KEY'
);

CREATE TABLE project_commands (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  label TEXT NOT NULL,
  command TEXT NOT NULL,
  run_in TEXT NOT NULL DEFAULT 'terminal',  -- 'terminal' | 'background'
  confirm_required INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE stack_items (
  id TEXT PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,     -- 'supabase' | 'nextjs' | 'shadcn' | ...
  name TEXT NOT NULL,
  kind TEXT,                     -- 'frontend' | 'backend' | 'db' | 'deploy' | 'lib' | 'service' | 'model'
  icon_url TEXT
);

CREATE TABLE project_stack (
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  stack_item_id TEXT NOT NULL REFERENCES stack_items(id),
  role TEXT,                     -- 'primary' | 'secondary'
  PRIMARY KEY (project_id, stack_item_id)
);

CREATE TABLE tags (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  color TEXT,
  UNIQUE (workspace_id, name)
);

CREATE TABLE project_tags (
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (project_id, tag_id)
);
```

### 4.3 Ship loop

```sql
CREATE TABLE sessions (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  started_at TIMESTAMPTZ NOT NULL,
  ended_at TIMESTAMPTZ,
  summary TEXT,
  files_touched JSONB DEFAULT '[]'::jsonb,
  commits JSONB DEFAULT '[]'::jsonb,
  next_step TEXT,
  source TEXT NOT NULL           -- 'skill' | 'manual' | 'cli'
);

CREATE TABLE decisions (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  title TEXT NOT NULL,
  context TEXT,
  decision TEXT NOT NULL,
  consequences TEXT,
  reconsider_if TEXT
);

CREATE TABLE ideas (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  body TEXT NOT NULL,
  source TEXT,                   -- 'web' | 'ios' | 'email' | 'skill'
  status TEXT NOT NULL DEFAULT 'inbox'  -- 'inbox' | 'triaged' | 'discarded'
);

CREATE TABLE ships (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  shipped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  version TEXT,
  summary TEXT,
  changelog_md TEXT
);

CREATE TABLE launches (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  platform TEXT NOT NULL,        -- 'ph' | 'hn' | 'x' | 'reddit' | 'newsletter'
  launched_at TIMESTAMPTZ NOT NULL,
  url TEXT,
  metrics JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE lifecycle_events (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  at TIMESTAMPTZ NOT NULL,
  kind TEXT NOT NULL,            -- 'first_commit' | 'first_user' | 'first_payment' | 'mrr_100' | 'mrr_1k' | 'ph_launch' | 'viral' | custom
  detail JSONB
);

CREATE TABLE notes (
  project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
  markdown TEXT NOT NULL DEFAULT '',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 4.4 Cost and revenue

```sql
CREATE TABLE ai_providers (
  slug TEXT PRIMARY KEY,         -- 'anthropic' | 'openai' | 'groq' | ...
  name TEXT NOT NULL
);

CREATE TABLE ai_keys (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  provider TEXT NOT NULL REFERENCES ai_providers(slug),
  label TEXT,
  project_id TEXT REFERENCES projects(id),    -- null = shared across projects
  ciphertext TEXT NOT NULL       -- encrypted with user-derived key
);

CREATE TABLE ai_spend_daily (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  project_id TEXT REFERENCES projects(id),
  provider TEXT NOT NULL REFERENCES ai_providers(slug),
  model TEXT,
  date DATE NOT NULL,
  input_tokens BIGINT DEFAULT 0,
  output_tokens BIGINT DEFAULT 0,
  cost_usd NUMERIC(10, 4) DEFAULT 0
);

CREATE TABLE infra_spend_daily (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,        -- 'hetzner' | 'vercel' | 'supabase' | ...
  date DATE NOT NULL,
  cost_usd NUMERIC(10, 4) DEFAULT 0,
  detail JSONB
);

CREATE TABLE stripe_accounts (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  project_id TEXT REFERENCES projects(id),
  stripe_account_id TEXT NOT NULL,
  connected_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE mrr_daily (
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  date DATE NOT NULL,
  mrr_usd NUMERIC(10, 2) NOT NULL,
  new_customers INTEGER DEFAULT 0,
  lost_customers INTEGER DEFAULT 0,
  PRIMARY KEY (project_id, date)
);

CREATE TABLE subscriptions_owned (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,            -- 'Linear' | 'Notion' | ...
  monthly_cost_usd NUMERIC(10, 2),
  renews_on DATE,
  attributed_project_ids JSONB DEFAULT '[]'::jsonb
);
```

### 4.5 Knowledge vault

```sql
CREATE TABLE prompts (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
  title TEXT NOT NULL,
  current_version_id TEXT,
  tags JSONB DEFAULT '[]'::jsonb,
  is_public INTEGER DEFAULT 0,
  UNIQUE (workspace_id, slug)
);

CREATE TABLE prompt_versions (
  id TEXT PRIMARY KEY,
  prompt_id TEXT NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
  body TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  notes TEXT
);

CREATE TABLE specs (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  project_id TEXT REFERENCES projects(id),
  slug TEXT NOT NULL,
  title TEXT NOT NULL,
  body_md TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (workspace_id, slug)
);

CREATE TABLE skills (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  body_md TEXT NOT NULL,
  is_public INTEGER DEFAULT 0,
  UNIQUE (workspace_id, slug)
);

CREATE TABLE templates (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  stack JSONB NOT NULL,
  files JSONB NOT NULL,
  UNIQUE (workspace_id, slug)
);

CREATE TABLE snippets (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  language TEXT,
  body TEXT NOT NULL,
  tags JSONB DEFAULT '[]'::jsonb
);
```

### 4.6 Inventory, customer loop, health

```sql
CREATE TABLE domains (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  registrar TEXT,
  status TEXT NOT NULL,          -- 'live' | 'parked' | 'for_sale' | 'dormant' | 'redirect'
  redirect_target TEXT,
  expires_on DATE,
  project_id TEXT REFERENCES projects(id),
  estimated_value_usd NUMERIC(10, 2)
);

CREATE TABLE assets (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,            -- 'favicon' | 'og_image' | 'logo' | 'screenshot'
  url TEXT NOT NULL,
  version INTEGER DEFAULT 1,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE feedback_items (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source TEXT NOT NULL,          -- 'email' | 'x' | 'discord' | 'form' | 'manual'
  body TEXT NOT NULL,
  classification TEXT,           -- 'bug' | 'feature' | 'praise' | 'complaint' | 'other'
  status TEXT NOT NULL DEFAULT 'new',  -- 'new' | 'triaged' | 'replied' | 'closed'
  convert_target TEXT            -- 'idea' | 'decision' | null
);

CREATE TABLE beta_members (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  invited_at TIMESTAMPTZ,
  first_active_at TIMESTAMPTZ,
  last_active_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'invited'  -- 'invited' | 'active' | 'silent' | 'churned'
);

CREATE TABLE integrations (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  project_id TEXT REFERENCES projects(id),
  kind TEXT NOT NULL,            -- 'github' | 'vercel' | 'stripe' | 'plausible' | ...
  config JSONB NOT NULL,
  token_ciphertext TEXT,
  connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE health_snapshots (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  taken_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  git_days_since_commit INTEGER,
  git_days_since_push INTEGER,
  uptime_ok INTEGER,
  ssl_days_left INTEGER,
  domain_days_left INTEGER,
  open_issues INTEGER,
  open_prs INTEGER,
  stars INTEGER,
  dependabot_alerts INTEGER,
  momentum_score NUMERIC(5, 2)
);

CREATE TABLE heartbeats (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  token TEXT UNIQUE NOT NULL,
  expected_every_seconds INTEGER NOT NULL,
  last_ping_at TIMESTAMPTZ
);
```

### 4.7 Legal

```sql
CREATE TABLE legal_entities (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  kind TEXT,                     -- 'llc' | 'gmbh' | 'personal' | 'sarl' | ...
  country TEXT,
  vat_id_ref TEXT,               -- reference only, never the number
  notes TEXT
);

CREATE TABLE compliance_records (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,            -- 'privacy_policy' | 'terms' | 'imprint' | 'cookie_policy' | 'dpa'
  url TEXT,
  last_reviewed_on DATE,
  review_due_on DATE
);
```

### 4.8 Search

```sql
CREATE INDEX projects_fts ON projects USING gin (to_tsvector('english', name || ' ' || coalesce(pitch, '')));
-- similar GIN tsvector indexes on sessions.summary, decisions.*, notes.markdown,
-- specs.body_md, prompts/prompt_versions.body, snippets.body, feedback_items.body
```

A single `/search?q=` endpoint federates across all searchable tables.

---

## 5. API surface

FastAPI REST over HTTPS + WebSocket channel for live updates. Auth: bearer token in `Authorization` header (user session token for web, device token for CLI).

### Shape

```
GET    /v1/me
GET    /v1/workspaces
GET    /v1/workspaces/:slug

# Projects
GET    /v1/projects?status=&tag=&q=
POST   /v1/projects
GET    /v1/projects/:slug
PATCH  /v1/projects/:slug
DELETE /v1/projects/:slug
POST   /v1/projects/:slug/switch                # set active

GET    /v1/projects/:slug/context
PATCH  /v1/projects/:slug/context

GET    /v1/projects/:slug/sessions?limit=
POST   /v1/projects/:slug/sessions

GET    /v1/projects/:slug/decisions
POST   /v1/projects/:slug/decisions

POST   /v1/projects/:slug/ideas
POST   /v1/projects/:slug/ships
POST   /v1/projects/:slug/launches

GET    /v1/projects/:slug/health
GET    /v1/projects/:slug/health/history

POST   /v1/projects/:slug/commands/:label/run   # streams over WS

# Knowledge
GET    /v1/prompts?q=
GET    /v1/prompts/:slug
POST   /v1/prompts
POST   /v1/prompts/:slug/versions
POST   /v1/prompts/:slug/run                    # model + inputs

GET    /v1/specs?q=
GET    /v1/specs/:slug
POST   /v1/specs

GET    /v1/snippets?q=

# Cost & revenue
GET    /v1/ai/spend?project=&from=&to=
GET    /v1/ai/keys
POST   /v1/ai/keys
GET    /v1/revenue/mrr
GET    /v1/revenue/pnl

# Inventory
GET    /v1/domains
POST   /v1/domains/import

# Feedback
GET    /v1/feedback?project=&status=
PATCH  /v1/feedback/:id

# Search
GET    /v1/search?q=

# Integrations
GET    /v1/integrations
POST   /v1/integrations/:kind/connect
DELETE /v1/integrations/:kind

# CLI pairing
POST   /v1/cli/pair/start
POST   /v1/cli/pair/complete

# Public
GET    /public/:workspace                       # portfolio page
GET    /public/:workspace/:slug                 # project page
GET    /public/:workspace.rss

# Webhooks
POST   /webhooks/stripe
POST   /webhooks/github
POST   /webhooks/vercel
POST   /webhooks/inbox/:token                   # email-to-inbox
POST   /webhooks/heartbeat/:token               # cron heartbeats

# WS
WS     /v1/ws                                   # live project updates, command streams
```

---

## 6. CLI specification

Single static Rust binary. Installs daemon via `launchd` (macOS), `systemd --user` (Linux), scheduled task (Windows). Daemon binds to `127.0.0.1:7421`.

### Commands

```
hangar pair                    # device-code flow, stores token in OS keychain
hangar unpair
hangar status                  # daemon + sync status
hangar sync                    # force full sync
hangar scan [path]             # scan folder for git repos, import as projects
hangar switch <slug>           # set active project
hangar active                  # print active project slug
hangar open <slug>             # open in browser / editor / SSH shortcut
hangar run <label>             # run saved project command
hangar brief <slug>            # print resurrection brief to stdout
hangar claude-md <slug>        # print generated CLAUDE.md
hangar skill install           # install/update Claude skill
hangar mcp-token               # print current MCP bearer token
hangar logs                    # tail daemon logs
hangar doctor                  # diagnose common issues
hangar version
```

### Daemon responsibilities

1. Hosts HTTP MCP server on `127.0.0.1:7421/mcp`.
2. Maintains local SQLite cache at `~/.hangar/cache.sqlite`.
3. WebSocket connection to cloud for live sync.
4. Filesystem operations: scan repos, read `.git`, read `~/.ssh/config`, open terminal with pre-filled commands.
5. Resolves secret references on demand via `op`, `bw`, or ssh-agent — secrets touch clipboard only.
6. Writes `.hangar-session` file into active project's repo root for shell/agent discovery.
7. Watches `.git/HEAD` of active project repo to detect branch changes, auto-logs.

### Filesystem layout

```
~/.hangar/
├── config.toml
├── cache.sqlite
├── backups/
├── cache/
│   ├── screenshots/
│   └── favicons/
└── logs/
    └── hangar.log
```

---

## 7. MCP tool surface

Exposed by the CLI daemon at `http://127.0.0.1:7421/mcp`. Bearer token from pairing, displayed via `hangar mcp-token`. All calls respect the currently active project unless a slug is explicit.

### Tools

**Read**
- `hangar.ping()` → `{ ok: true, version, active: slug }`
- `hangar.active()` → full active project (identity, context, stack, infra, links, last 3 sessions, last 5 decisions, latest health)
- `hangar.list(filter?)` → `[{ slug, name, status, emoji, momentum }]`
- `hangar.get(slug)` → same shape as `active()` for the given project
- `hangar.brief(slug?)` → resurrection brief (string)
- `hangar.health(slug?)` → latest health snapshot
- `hangar.search(q)` → `[{ entity, entity_id, project_slug, snippet }]`
- `hangar.prompts.search(q)` / `hangar.prompts.get(slug)`
- `hangar.specs.search(q)` / `hangar.specs.get(slug)`
- `hangar.snippets.search(q)`
- `hangar.recent_sessions(slug?, n?)`
- `hangar.decisions(slug?)`

**Write**
- `hangar.switch(slug)` → `{ active: slug }`
- `hangar.log_session({ summary, files_touched?, commits?, next_step? }, slug?)`
- `hangar.update_context({ current_focus?, next_step?, user_wants?, open_questions?, known_issues?, blocked_by? }, slug?)`
- `hangar.decision({ title, context, decision, consequences, reconsider_if? }, slug?)`
- `hangar.idea(text, slug?)`
- `hangar.ship({ version?, summary }, slug?)` → generates changelog, drafts tweets, logs event
- `hangar.note_append(markdown, slug?)`
- `hangar.link_add({ kind, label, url }, slug?)`
- `hangar.status(status, slug?)` → change project status

**Execute**
- `hangar.run(label, slug?)` → run saved command, stream output (requires user confirmation unless pre-approved for that label)
- `hangar.claude_md(slug?)` → return generated `CLAUDE.md` string; writing to repo root is opt-in
- `hangar.handover(slug?)` → generate full onboarding brief (string)

**Hub relay (transparent to client)**
- When active project has sub-MCPs configured (Stripe, Supabase, Vercel, custom), Hangar mounts their tools under their original names into the same MCP listing. Claude Code sees one unified tool list that changes as the active project changes.

### Auth

Bearer token. Generated on CLI pair. Rotatable via `hangar mcp-token --rotate`. Never sent to cloud.

---

## 8. Claude skill

Installed by `hangar skill install` into the user's Claude skills directory.

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

# Hangar — project context for Claude Code

## On session start (first action of every session)
1. hangar.ping(). If unreachable, surface a subtle note and continue without context.
2. hangar.active() → internalize identity, stack, infra, current_focus, next_step,
   user_wants, open_questions, last 3 sessions.
3. If repo.local_path does not match the current working directory, warn the user
   and ask whether to switch active project.
4. Open with: "Working on **<n>**. Last session (<when>): <summary>.
   Next step: <next_step>. Open questions: <open_questions summary>. Continue?"

## During session
- When user mentions past work, consult hangar.prompts.search / hangar.specs.search
  before answering from memory.
- When user says "what did I decide about X" → hangar.search(X), filter to decisions.
- When user says "switch to <slug>" → hangar.switch(slug) → reload context.
- When user says "capture this idea: …" → hangar.idea(text).
- When user asks "what's on fire" → hangar.health() across projects.

## On session end (user says "done", "log this", "commit and stop", "ship it")
- Summarize what was done in 1–3 sentences.
- Infer next_step from unfinished work.
- hangar.log_session({ summary, files_touched, commits, next_step }).
- If next_step changed, hangar.update_context({ next_step }).
- If user said "ship it" → hangar.ship({ version, summary }) → walk through the
  generated changelog and tweet drafts for approval.
- Confirm: "Logged. Next: <next_step>."

## Hard rules
- Never invent project data. If a field is empty, say so.
- Never persist secrets to Hangar. If user pastes one, reject and remind them to
  use a project_secret_ref instead.
- All writes go through MCP tools, never by touching ~/.hangar files directly.
- When referencing a prompt or spec from the vault, cite it by slug in the
  session log so the trail is preserved.
```

---

## 9. Public pages

Two public surfaces per workspace, fully static-rendered with ISR:

- `hangar.dev/<workspace>` — portfolio page listing all public projects with emoji, status, pitch, last ship, live URL.
- `hangar.dev/<workspace>/<slug>` — per-project page: hero (name, pitch, live URL, status), stack, changelog feed, lifecycle events, optional metrics (commits, MRR, stars), decision log if marked public, "built with Hangar" footer.

Both pages have RSS feeds. Custom domains available on Studio tier (e.g. `now.lenny.services`).

SEO: server-rendered, OG images auto-generated, structured data, sitemap, robots.txt. First-party analytics via self-hosted Plausible — no third-party trackers.

---

## 10. Pricing and tiers

- **Free** — up to 3 projects, local CLI, basic registry + context, MCP, skill. No integrations. No public pages.
- **Pro — $12/mo or $120/yr** — unlimited projects, all integrations, AI cost dashboard, health monitoring, public pages on `hangar.dev/<workspace>`, knowledge vault, iOS + browser extension.
- **Studio — $24/mo** — everything in Pro plus custom domain on public pages, unlimited AI provider integrations, advanced automations, priority support.
- **Team — $16/user/mo (5-user minimum)** — shared workspaces, role-based access, shared knowledge vault, team portfolio view.
- **Self-host** — Hangar Core (API + CLI + skill) is MIT licensed. Runnable via Docker Compose. Cloud sync and public pages are the paid convenience.

Stripe Billing. EU VAT handled via Stripe Tax. Annual plans discounted 2 months.

---

## 11. Tech stack (committed)

| Layer | Choice |
|---|---|
| Frontend | Vue 3 + TypeScript + Vite + Pinia |
| UI kit | Tailwind + shadcn-vue + Lucide |
| Backend | FastAPI + SQLAlchemy + Pydantic v2 + Alembic |
| DB | Postgres 16, self-hosted on Hetzner (primary) with daily encrypted offsite backup |
| Cache | Redis (sessions, rate-limit, worker queue) |
| Workers | Celery with Redis broker |
| Auth | Custom magic-link + passkeys (FastAPI + `py_webauthn`) |
| Billing | Stripe + Stripe Tax |
| Hosting | Hetzner VPS, Docker Compose, Caddy reverse proxy, automatic TLS |
| CDN / DNS | Cloudflare (DNS only; no proxy for app traffic) |
| Object storage | Hetzner Object Storage (S3-compatible) |
| Analytics | Self-hosted Plausible |
| Email | Resend for transactional, custom MX for inbox forwarding |
| CLI | Rust, single static binary via `cargo build --release` + `cross` for cross-compile |
| MCP | `rmcp` crate, HTTP on `127.0.0.1:7421`, bearer token |
| CLI local cache | SQLite via `rusqlite` |
| CLI ↔ cloud | `tokio-tungstenite` for WS, `reqwest` for REST |
| iOS companion | Expo React Native |
| Browser extension | Manifest V3, vanilla TS + Vue |
| Monitoring | Self-hosted Prometheus + Grafana, uptime via external ping |
| CI/CD | GitHub Actions, Docker image build + push, deploy via SSH |

---

## 12. Naming

Final: **Hangar**. Metaphor: you command a hangar of aircraft; some flying, some parked, some in maintenance. Short, visual, ownable, no dev-tool conflicts. Primary domain target: `hangar.dev`. Fallbacks: `hangar.sh`, `hangar.so`, `flyhangar.com`.

---

## 13. Core loop (putting it together)

1. Open Claude Code in a project directory.
2. Skill auto-calls `hangar.active()` → if directory matches, context loads; otherwise prompts to switch.
3. Claude Code opens with your last state, reads your mind on next step.
4. You work. Changes logged implicitly.
5. You say "ship it" → Hangar generates changelog, drafts tweets, updates public page, logs ship event.
6. Tweet goes out; X impressions feed back into the project's timeline.
7. A user replies with feedback; email forward hits project inbox.
8. Stripe pings a new subscription; MRR updates; lifecycle event fires.
9. You open hangar.dev the next morning. Weekly review email suggests killing one project, doubling down on another.
10. You switch active project with `Cmd+K`. Loop continues.

This loop is the product.

---

## 14. Key differentiators

1. Only tool where Claude Code instantly knows your entire project portfolio via MCP.
2. Only tool with cross-provider AI cost attribution per project.
3. MCP hub relay — active project determines tool belt.
4. Ship loop is a first-class primitive, not a side effect.
5. Public project pages built-in.
6. Local-first, self-hostable, MIT core.
7. Built by a vibecoder for vibecoders.

---

## 15. Example artifacts

### 15.1 Example generated `CLAUDE.md`

```markdown
# Butlr

OpenClaw-as-a-Service SaaS. Users spin up isolated Claude agent VMs on demand.

## Stack
- Frontend: Next.js 15, Tailwind, shadcn
- Backend: FastAPI, Python 3.12
- DB: Postgres via Supabase
- Deploy: Vercel (frontend), Hetzner VPS (backend)

## Infra
- Server: SSH alias `butlr-prod`
- Domain: butlr.cloud (Cloudflare DNS)
- DB: Supabase project `butlr-prod`
- Secrets: reference vault "Butlr" in 1Password

## Current state
- Focus: Stripe webhook for subscription events
- Next: Handle `customer.subscription.deleted` → tear down VM
- User wants: Monthly + annual billing
- Open questions: Pro-rata on mid-cycle upgrades?
- Blocked by: —

## Recent sessions
- 2d ago — Finished OpenClaw VM spin-up on Hetzner API. Tested with 3 concurrent VMs. Files: `backend/vm/provisioner.py`, `backend/api/routes/vms.py`.
- 5d ago — Stripe setup, product + price IDs configured.

## Decisions
- Hetzner API over DO (cheaper, closer to EU users, simpler API).
- Supabase over self-hosted PG (faster to ship, auth included).

## Commands
- Deploy backend: `ssh butlr-prod "cd butlr && git pull && docker compose up -d --build"`
- Tail logs: `ssh butlr-prod "docker compose logs -f api"`

Generated by Hangar.
```

### 15.2 Example MCP call/response

```
→ hangar.active()

← {
  "slug": "butlr",
  "name": "Butlr",
  "emoji": "🛎️",
  "status": "building",
  "context": {
    "current_focus": "Stripe webhook for subscription events",
    "next_step": "Handle customer.subscription.deleted → tear down VM",
    "user_wants": "Monthly + annual billing",
    "open_questions": ["Pro-rata on mid-cycle upgrades?"]
  },
  "repo": {
    "git_url": "git@github.com:lennystepn-hue/butlr.git",
    "local_path": "/Users/lenny/code/butlr",
    "default_branch": "main"
  },
  "stack": { "frontend": "Next.js 15", "backend": "FastAPI", "database": "Supabase Postgres" },
  "infra": { "server_alias": "butlr-prod", "domain_primary": "butlr.cloud" },
  "recent_sessions": [ /* last 3 */ ],
  "latest_health": { "ssl_days_left": 82, "uptime_ok": true, "git_days_since_commit": 2 }
}
```

### 15.3 Example `log_session` payload

```json
{
  "summary": "Implemented Stripe subscription webhook handler. Tested deletion and update events with Stripe CLI. VM teardown now fires correctly on cancellation.",
  "files_touched": [
    "backend/billing/webhook.py",
    "backend/vm/teardown.py",
    "tests/billing/test_webhook.py"
  ],
  "commits": [
    { "sha": "a3f12b9", "msg": "feat: stripe subscription webhook + vm teardown" }
  ],
  "next_step": "Handle pro-rata on mid-cycle plan upgrades — check Stripe docs for subscription.updated proration preview."
}
```

### 15.4 Example resurrection brief

```
Butlr — OpenClaw-as-a-Service. Last touched 94 days ago.

What it is: SaaS that provisions isolated Claude agent VMs for users on demand via the Hetzner Cloud API, Stripe-billed.

Where it stands: Backend scaffolded, VM spin-up working, Stripe subscription webhook half-implemented. Frontend is a minimal Next.js landing + dashboard. One paying test user. Not yet publicly launched.

What broke: SSL on butlr.cloud expires in 12 days. Dependabot flagged a medium CVE in the FastAPI stack. Last deploy 94 days ago, so CI is likely broken.

What you were about to do: Finish the customer.subscription.deleted handler so cancelled subs actually tear down VMs. There's an open question about pro-rata on mid-cycle plan upgrades you never resolved.

Suggested first move: Renew SSL, run dependabot updates, re-run CI, then pick up the subscription.deleted handler. Estimated 3-hour re-onboarding.
```

---

## 16. Build order (not phases, just dependency order)

When Claude Code starts building, the dependency graph is:

1. **Database schema** — all migrations from §4.
2. **Auth + workspaces** — §4.1 plus magic-link flow.
3. **Projects CRUD** — §4.2, REST endpoints from §5.
4. **Web dashboard shell** — Vue SPA, three-pane layout, Cmd+K palette, project list + detail.
5. **CLI skeleton** — `hangar pair`, `hangar status`, daemon process, local SQLite cache, WS sync.
6. **MCP server in CLI daemon** — all tools from §7, auth token, tests with MCP Inspector.
7. **Hangar skill** — §8, installable via `hangar skill install`.
8. **Ship loop** — §4.3 tables, ship button flow, changelog generation.
9. **Health worker** — §4.6 background worker, polling GitHub + uptime + SSL.
10. **AI cost dashboard** — §4.4, provider connectors for Anthropic and OpenAI first.
11. **Public pages** — §9, static rendering, OG images.
12. **Knowledge vault** — §4.5, prompt runner.
13. **Integrations** — Stripe, Vercel, Cloudflare in that order.
14. **Billing** — Stripe subscriptions for Pro/Studio.
15. **Feedback inbox** — email MX, X integration.
16. **Domain inventory** — Cloudflare + Namecheap APIs.
17. **iOS companion + browser extension**.

Each step leaves the product usable. Dogfood throughout.

---

**End of specification.**
