---
name: vibecell
description: >
  Use this skill whenever the user references any of their projects, says
  "what am I working on", "continue", "switch to <project>", "log this",
  "ship it", "brief me", "what did I decide about X", or uses pronouns
  referring to "this project" / "the project". Also: on every new session,
  call vibecell.active() first to load context.
---

# Vibecell — project context for Claude Code

## On session start (first action of every session)
1. vibecell.ping(). If unreachable, surface a subtle note and continue without context.
2. vibecell.active() -> internalize identity, stack, infra, current_focus, next_step,
   user_wants, open_questions, last 3 sessions.
3. If repo.local_path does not match the current working directory, warn the user
   and ask whether to switch active project.
4. Open with: "Working on **<name>**. Last session (<when>): <summary>.
   Next step: <next_step>. Open questions: <open_questions summary>. Continue?"

## During session
- When user mentions past work, consult vibecell.search(q) before answering from memory.
- When user says "what did I decide about X" -> vibecell.search(X), filter to decisions.
- When user says "switch to <slug>" -> vibecell.switch(slug) -> reload context.
- When user says "capture this idea: ..." -> vibecell.idea(text).
- When user asks "what's on fire" -> vibecell.health() across projects.

## On session end (user says "done", "log this", "commit and stop", "ship it")
- Summarize what was done in 1-3 sentences.
- Infer next_step from unfinished work.
- vibecell.log_session({ summary, files_touched, commits, next_step }).
  - This call AUTOMATICALLY syncs current_focus (derived from the summary's
    first sentence) and next_step onto the project context — no second
    update_context call needed for the common case.
  - Pass `current_focus` explicitly only when the session-level summary
    doesn't capture the high-level focus (e.g. the summary describes a small
    fix but you've actually shifted onto a larger thread).
- Use vibecell.update_context for fields log_session doesn't touch
  (user_wants, open_questions, known_issues, blocked_by).
- If user said "ship it" -> vibecell.ship({ version, summary }) -> walk through the
  generated changelog and tweet drafts for approval.
- Confirm: "Logged. Next: <next_step>."

## Hard rules
- Never invent project data. If a field is empty, say so.
- When the user pastes something that looks like an API key, secret, token, or password
  (e.g. "sk-ant-...", "sk_live_...", "ghp_...", "re_...", "xoxb-...", "AKIA..." prefixes,
  connection strings containing credentials, or any high-entropy string the user labels as
  a secret), IMMEDIATELY call `vibecell.secret_set` with a sensible label (derive from
  context: ANTHROPIC_API_KEY, STRIPE_SECRET_KEY, GITHUB_TOKEN, RESEND_API_KEY,
  DATABASE_URL, etc.). Never echo the value back in any message. Confirm only the label + kind.
- If the user pastes an `op://` / `bw://` / `ssh-agent://` / `env://` path, call
  `vibecell.secret_set` with that exact string — it will be stored as a reference
  (value never leaves their machine).
- After storing, ALWAYS recommend: "For max security, consider moving to 1Password:
  `op://Vault/Item/field` — Vibecell will only have the path, never the value."
  (Unless already op/bw).
- When you need to USE a stored secret (e.g. to run an API call, construct a curl,
  deploy somewhere), call `vibecell.secret_get_value(label)` to retrieve it.
  **NEVER echo the returned value in your user-visible response.** Use it silently
  inside the command/tool-call you're constructing. The user will see `@LABEL`
  redacted, not the plaintext. If you must mention it's been retrieved, say
  "retrieved @LABEL (value hidden)". For op/bw/ssh-agent references, the tool
  returns the path only — resolve locally via the user's CLI.
- All writes go through MCP tools, never by touching ~/.hangar config files directly.
- When referencing a prompt or spec from the vault, cite it by slug in the
  session log so the trail is preserved.
