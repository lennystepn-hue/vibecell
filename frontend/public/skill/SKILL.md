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
   user_wants, open_questions, last 3 sessions.
3. If repo.local_path does not match the current working directory, warn the user
   and ask whether to switch active project.
4. Open with: "Working on **<name>**. Last session (<when>): <summary>.
   Next step: <next_step>. Open questions: <open_questions summary>. Continue?"

## During session
- When user mentions past work, consult vibecell_search(q) before answering from memory.
- When user says "what did I decide about X" -> vibecell_search(X), filter to decisions.
- When user says "switch to <slug>" -> vibecell_switch(slug) -> reload context.
- When user says "capture this idea: ..." -> vibecell_idea(text).
- When user asks "what's on fire" -> vibecell_health() across projects.

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

## On session end (user says "done", "log this", "commit and stop", "ship it")
- Summarize what was done in 1-3 sentences.
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
