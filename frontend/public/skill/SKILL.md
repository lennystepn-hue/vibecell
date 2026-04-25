---
name: vibecell
description: >
  Use this skill whenever the user references any of their projects, says
  "what am I working on", "continue", "switch to <project>", "log this",
  "ship it", "brief me", "what did I decide about X", or uses pronouns
  referring to "this project" / "the project". Also: on every new session,
  call vibecell_active() first to load context.
---

# Vibecell — project context for Claude Code

## On session start (first action of every session)
1. vibecell_ping(). If unreachable, surface a subtle note and continue without context.
2. vibecell_active() -> internalize identity, stack, infra, current_focus, next_step,
   user_wants, open_questions, last 3 sessions, **env_status**.
3. **vibecell_audit()** -> get the pre-flight gap list. Every `gap` in the result has
   a concrete `action` pointing to the tool that fixes it. Work through them OR flag
   the top 2-3 to the user ("btw: no environments recorded, no current_focus set") so
   the project card stays complete WITHOUT the user having to notice and ask. Non-
   negotiable for the first session on a project; skip only if all gaps are `[]`.
4. If repo.local_path does not match the current working directory, warn the user
   and ask whether to switch active project.
4. **Auto-catalog / drift check** — branch on `env_status`:
   - `env_status.needs_initial_scan === true` → this project has never been scanned
     (naked stack/infra, no fingerprint). Read the manifest files that exist in
     `cwd` (see "Which manifests to read" below) and call `vibecell_sync_repo({
       local_path: <cwd>,
       manifests: { "<path>": "<file-content>", ... }
     })`. This is a ONE-TIME catalog — you're teaching Vibecell what this project
     actually IS (stack, infra, pitch) without the user having to type it.
   - `env_status.has_fingerprint === true` → project already catalogued. Read the
     SAME manifest set and call `vibecell_check_env_drift({ manifests: {...} })`.
     If `drifted: true` → summarise what changed (e.g. "package.json added: react-query,
     pyproject.toml removed: requests") and offer `vibecell_sync_repo(..., force:false)`
     to refresh stack/infra. If `drifted: false` → silent, continue.
   - `env_status.needs_initial_scan === false` && `has_fingerprint === false` → the
     project has stack/infra already but no fingerprint (legacy GitHub-imported project).
     Call `vibecell_sync_repo` once with `force:false` to establish a baseline fingerprint
     for future drift checks.
5. Open with: "Working on **<name>**. Last session (<when>): <summary>.
   Next step: <next_step>. Open questions: <open_questions summary>. Continue?"
   (If initial_scan ran, add one line: "Catalogued <N> stack items, <M> tags.")
   (If drift detected, add one line: "⚠️ env changed since last session: <files>.")

### Which manifests to read (curated list)
Read whichever of these exist in `cwd` with the Read tool (skip missing ones, don't fail):

- `README.md` (primary — describes what the project is)
- `package.json` (Node/TS deps + scripts)
- `pyproject.toml` OR `requirements.txt` (Python)
- `Cargo.toml` (Rust)
- `go.mod` (Go)
- `composer.json` (PHP)
- `Gemfile` (Ruby)
- `Dockerfile`, `docker-compose.yml` / `compose.yml` (runtime infra)
- `.env.example` / `env.example` (env-var contract — NEVER the real `.env`)

Cap each file at ~8000 chars before sending (the server caps anyway). Send them all
in one `manifests` dict — one tool call, not one per file.

**Never read `.env` itself.** Only `.env.example`.

## During session
- When user mentions past work, consult vibecell_search(q) before answering from memory.
- When user says "what did I decide about X" -> vibecell_search(X), filter to decisions.
- When user says "switch to <slug>" -> vibecell_switch(slug) -> reload context.
- When user says "capture this idea: ..." -> vibecell_idea(text).
- When user asks "what's on fire" -> vibecell_health() across projects.

## NON-NEGOTIABLE auto-logging rules (the heart of Vibecell)
The whole point of this skill is that the dashboard stays in sync with what
you actually did, **without the user ever having to remind you**. If they have
to ask "did you log that?", the product has failed. These rules fire even
when you're deep in flow:

### Rule 1 — Topic shift = `vibecell_update_context` (not optional)
When the conversation pivots to a meaningfully new piece of work, BEFORE you
start that work call `vibecell_update_context` with a fresh `current_focus` +
`next_step`. Examples of "topic shift":
  - User asks for a new feature ("now let's add Stripe webhooks")
  - User reports a bug to investigate ("the dropdown doesn't update")
  - You finish a multi-step task and surface the result
  - User says "let's switch to X for a bit"

`current_focus` should be 1 sentence, present-tense, what's happening RIGHT
NOW. `next_step` is the immediate concrete-action that comes after the
current move, NOT a 5-step plan.

### Rule 2 — Architectural choice = `vibecell_decision` (not optional)
Anytime the conversation produces a non-trivial choice that future-you (or
another maintainer) would want to find — an API shape, a library swap, a
design trade-off, a data model decision, a security stance — record it with
`vibecell_decision` with title / decision / context / consequences /
reconsider_if. The bar isn't "huge architectural change", it's "would I
search for this in 3 months when I forget why I did it?". Yes? Log it.

### Rule 3 — git commit = `vibecell_log_session` (already covered above
under "Auto-log after every git commit", but worth repeating). Never wait
for end-of-session to flush — log per commit, summary = first commit-
message line.

### Rule 4 — End of every assistant turn that did work: audit yourself
Before you respond to the user, scan what you just did in this turn. Ask
yourself: did I just (a) commit code, (b) make an architectural choice, OR
(c) shift the topic? If yes to ANY: the matching tool call HAS to have run
already in the same turn. If you forgot — call it now, then send your
response. Do NOT wait for the user to remind you.

The user should NEVER have to type "log that" or "did you update context".
If they do, you've broken the rule.

## Creating a new project from a concept
When the user describes a new project idea with phrases like "I want to build X",
"let's start a new project called Y", "erstelle ein projekt für Z", "baue ein neues
projekt", "spawn a project", or any similar intent — do NOT wait for them to click
"+ New project" in the UI. Instead:

1. If the concept is still fuzzy, ask 1-2 clarifying questions (name? what does it
   DO? any tech stack hint?). Keep it short — we want the project live before the
   user loses flow.

2. Once you have a name + a rough pitch, call `vibecell_create_project` with as much
   structured info as the conversation gave you. Example:
   ```
   vibecell_create_project({
     name: "Giftmakr Analytics",
     pitch: "Dashboard for tracking gift recommendations + conversion rates",
     emoji: "📊",
     status: "idea",  // default
     tags: ["analytics", "saas"],
     stack: [
       {slug: "vue-3", name: "Vue 3", kind: "framework", role: "frontend"},
       {slug: "fastapi", name: "FastAPI", kind: "framework", role: "backend"}
     ],
     github_url: "https://github.com/user/giftmakr-analytics"  // optional
   })
   ```

3. The tool returns `{slug, url, stats}`. Surface the URL to the user — "Created
   **Giftmakr Analytics** → https://vibecell.dev/p/giftmakr-analytics (now your
   active project). I pre-filled <N> stack items, <N> tags, <N> environments."

4. The project is set as active by default. Follow-up work (todos, first session log,
   decisions, etc.) goes to the new project without needing `vibecell_switch`.

Be generous with inference: if the user mentions "Vue + Postgres + Docker" put all
three in `stack`. If they say "will live at foo.com" set `environments: [{kind:
"prod", url: "https://foo.com"}]`. The tool is idempotent via the same dedup writer
as GitHub import, so over-specifying is safe.

## Auto-TODO flow (plan → work → tick)
**When the user asks for something involving 3+ distinct steps** (a feature,
a refactor, a migration, a launch push), do NOT silently start coding. Plan
the work as a visible batch of todos first so the user can watch progress
on the dashboard in real time:

1. First tool call: `vibecell_todo_batch_add({
     batch: "<short-slug-for-this-work>",
     titles: ["<step 1>", "<step 2>", ...]
   })`
   Keep batch names short and kebab-case (e.g. "stripe-webhook",
   "auth-refactor", "v0.9-launch"). Titles should be imperative and
   concrete ("Add migration for X", not "Think about X").

2. For each todo, in order:
   - `vibecell_todo_start({ todo_id })` — the dashboard highlights this
     one as "◉ claude is on this".
   - Do the actual work (code, tests, migration, whatever).
   - `vibecell_todo_complete({ todo_id, completion_note: "<1-sentence
     proof of what shipped>" })` — the card ticks off with a green
     checkmark and the completion_note renders under it.

3. If the user's request clearly resolves in 1-2 trivial edits, skip the
   todo dance — it's overhead for a one-liner. Rule of thumb: if you'd
   normally split into multiple commits, it's worth the todo batch.

4. If the user interrupts or pivots mid-batch, you can:
   - Leave unused todos as `open` (user can delete later)
   - Cancel specific ones via `vibecell_todo_complete` with a note like
     "cancelled — user pivoted to X"

The goal: the user opens the dashboard and sees **visible progress
ticking off in real time** instead of a wall of silent code edits. This
is the core Vibecell UX — make AI work observable.

## Auto-log after every git commit (MECHANICAL — no keywords required)

Keyword-based session logging (see "On session end" below) is the FALLBACK.
The primary trigger is **mechanical: every time you make a git commit, log
immediately.** This closes the gap where long iterative fix sessions never
hit a "done" / "ship it" phrase and therefore never get logged — the
dashboard then silently drifts out of sync with what you actually built.

Rule:

1. After any successful `git commit` (or `git commit && git push`), BEFORE
   you respond to the user or start the next task, call:
   ```
   vibecell_log_session({
     summary: "<first line of the commit message>",
     commits: [{ sha: "<7-char sha>", msg: "<commit subject>" }],
     files_touched: [/* from `git status --short` output just before the commit */],
     next_step: "<what's the immediate next thing? if nothing, leave null>"
   })
   ```
2. If the commit closed an in_progress todo, also call
   `vibecell_todo_complete({ todo_id, completion_note: "<commit subject>" })`
   so the TodosCard ticks off in real time.
3. If the commit represents a material decision (architecture, security,
   public API, schema), record it with `vibecell_decision` — separate from
   the session log. One commit can produce both a session-log entry AND a
   decision entry.
4. **Safety-net**: if you realise you've made ≥3 commits since the last
   `vibecell_log_session` call, log now regardless — don't wait for the
   next commit. Batch the unlogged commits into one session entry with all
   their SHAs in the commits array.

Session summaries from auto-log should be ONE sentence pulled from the
commit subject. No prose. The project dashboard renders these live via
SSE — they should be scannable, not essays.

## On session end (user says "done", "log this", "commit and stop", "ship it")
- Summarize what was done in 1-3 sentences (more context than the per-commit
  auto-logs above — these are the "wrap-up" logs).
- Infer next_step from unfinished work.
- vibecell_log_session({ summary, files_touched, commits, next_step }).
  - This call AUTOMATICALLY syncs current_focus (derived from the summary's
    first sentence) and next_step onto the project context — no second
    update_context call needed for the common case.
  - Pass `current_focus` explicitly only when the session-level summary
    doesn't capture the high-level focus (e.g. the summary describes a small
    fix but you've actually shifted onto a larger thread).
- Use vibecell_update_context for fields log_session doesn't touch
  (user_wants, open_questions, known_issues, blocked_by).
- If user said "ship it" -> vibecell_ship({ version, summary }) -> walk through the
  generated changelog and tweet drafts for approval.
- Confirm: "Logged. Next: <next_step>."

## Hard rules
- Never invent project data. If a field is empty, say so.
- When the user pastes something that looks like an API key, secret, token, or password
  (e.g. "sk-ant-...", "sk_live_...", "ghp_...", "re_...", "xoxb-...", "AKIA..." prefixes,
  connection strings containing credentials, or any high-entropy string the user labels as
  a secret), IMMEDIATELY call `vibecell_secret_set` with a sensible label (derive from
  context: ANTHROPIC_API_KEY, STRIPE_SECRET_KEY, GITHUB_TOKEN, RESEND_API_KEY,
  DATABASE_URL, etc.). Never echo the value back in any message. Confirm only the label + kind.
- If the user pastes an `op://` / `bw://` / `ssh-agent://` / `env://` path, call
  `vibecell_secret_set` with that exact string — it will be stored as a reference
  (value never leaves their machine).
- After storing, ALWAYS recommend: "For max security, consider moving to 1Password:
  `op://Vault/Item/field` — Vibecell will only have the path, never the value."
  (Unless already op/bw).
- When you need to USE a stored secret (e.g. to run an API call, construct a curl,
  deploy somewhere), call `vibecell_secret_get_value(label)` to retrieve it.
  **NEVER echo the returned value in your user-visible response.** Use it silently
  inside the command/tool-call you're constructing. The user will see `@LABEL`
  redacted, not the plaintext. If you must mention it's been retrieved, say
  "retrieved @LABEL (value hidden)". For op/bw/ssh-agent references, the tool
  returns the path only — resolve locally via the user's CLI.
- All writes go through MCP tools, never by touching ~/.hangar config files directly.
- When referencing a prompt or spec from the vault, cite it by slug in the
  session log so the trail is preserved.
