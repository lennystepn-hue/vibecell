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
2. hangar.active() -> internalize identity, stack, infra, current_focus, next_step,
   user_wants, open_questions, last 3 sessions.
3. If repo.local_path does not match the current working directory, warn the user
   and ask whether to switch active project.
4. Open with: "Working on **<name>**. Last session (<when>): <summary>.
   Next step: <next_step>. Open questions: <open_questions summary>. Continue?"

## During session
- When user mentions past work, consult hangar.prompts.search / hangar.specs.search
  before answering from memory.
- When user says "what did I decide about X" -> hangar.search(X), filter to decisions.
- When user says "switch to <slug>" -> hangar.switch(slug) -> reload context.
- When user says "capture this idea: ..." -> hangar.idea(text).
- When user asks "what's on fire" -> hangar.health() across projects.

## On session end (user says "done", "log this", "commit and stop", "ship it")
- Summarize what was done in 1-3 sentences.
- Infer next_step from unfinished work.
- hangar.log_session({ summary, files_touched, commits, next_step }).
- If next_step changed, hangar.update_context({ next_step }).
- If user said "ship it" -> hangar.ship({ version, summary }) -> walk through the
  generated changelog and tweet drafts for approval.
- Confirm: "Logged. Next: <next_step>."

## Hard rules
- Never invent project data. If a field is empty, say so.
- Never persist secrets to Hangar. If user pastes one, reject and remind them to
  use a project_secret_ref instead.
- All writes go through MCP tools, never by touching ~/.hangar files directly.
- When referencing a prompt or spec from the vault, cite it by slug in the
  session log so the trail is preserved.
