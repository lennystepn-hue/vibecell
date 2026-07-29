"""The onboarding routine, served to the agent instead of pasted by the user.

Before this, the routine was frozen text in
`frontend/src/lib/installPrompt.ts`. A user who pasted it once could never
receive an improvement to it — the copy on their clipboard was the copy they
kept. Moving it behind a tool makes it server-side and editable, and shrinks
the thing the user actually pastes to two lines.

One tool, two modes, on purpose:

  * `vibecell_onboard()` → returns the routine
  * `vibecell_onboard(event=…)` → reports one step of it

Every MCP tool is context the agent re-reads on every session for the rest of
the account's life. A flow that runs exactly once per user does not get to
spend two slots on that.
"""
from __future__ import annotations

from app.mcp.auth import MCPContext
from app.services import onboarding_events as bus

# What the agent is told to do. Kept as prose rather than a rigid script
# because the agent is better than we are at the messy parts — deciding what
# counts as a real project, reading an unfamiliar build file — and worse at
# guessing what we want reported.
_ROUTINE = """\
# Vibecell onboarding

Set up this user's portfolio. Work through it end to end without stopping to
ask — they asked for exactly this when they ran the installer.

## 1. Find their projects

Look for git repositories under the user's usual code locations (the current
directory first, then common roots like ~/code, ~/src, ~/projects,
~/Developer, ~/repos). Depth 3 is plenty; do not crawl the whole home
directory.

Skip anything that is clearly not a project of theirs: node_modules, vendor,
.venv, target, dist, build, Go module caches, and clones of other people's
repos that they have no commits in.

Then call:

    vibecell_onboard(event="scan.started", repo_count=<how many you found>)

## 2. Create each project

For each repo, call `vibecell_create_project` with everything you can infer
without guessing:

  * **name** — the repo's own name, tidied for humans ("my-cool-api" → "My
    Cool API") unless the README clearly gives a real name
  * **pitch** — one sentence, from the README's first paragraph or the
    package description. Say what it *is*, not that it is "a project".
  * **stack** — from package.json / pyproject.toml / Cargo.toml / go.mod /
    Gemfile, plus obvious infra from docker-compose.yml, Dockerfile,
    vercel.json, fly.toml, netlify.toml
  * **status** — `live` if there is a deploy config and recent commits,
    `building` if there are commits in the last 90 days, `idea` if it is
    mostly empty, `paused` otherwise
  * **github_url** — from `git remote get-url origin`, if it is a GitHub URL

After each one:

    vibecell_onboard(event="project.created", slug=<slug>, name=<name>)

## 3. Enrich

For each created project, read enough to fill its context: the README beyond
the first paragraph, the last ~20 commit subjects, any TODO or ROADMAP file.
Then set `current_focus` and `next_step` via `vibecell_set_focus` — what the
commit history says they were last doing, and the obvious next move.

If a repo is genuinely dormant, say so in the focus rather than inventing
momentum. "Untouched since March; last work was the Stripe webhook" is more
useful than a cheerful guess.

After each one:

    vibecell_onboard(event="project.enriched", slug=<slug>, pitch=<pitch>)

## 4. Finish

    vibecell_onboard(event="done", project_count=<total created>)

Then tell the user, briefly: how many projects are in, which two or three
need attention and why (stale, no deploy, no context), and what you would do
first. No summary of the process — they watched it happen.

## Rules

  * Never invent data. An empty field is better than a plausible fiction, and
    the user will trust the whole portfolio less if they catch one made-up
    pitch.
  * Report each event as you go, not in a batch at the end. Someone is
    watching a screen fill up.
  * If a repo fails to read, skip it and carry on. One broken project must
    not cost them the other thirteen.
"""


async def handle_onboard(args, ctx: MCPContext) -> str:
    """Serve the routine, or report one step of it."""
    event = getattr(args, "event", None)

    if event is None:
        return _ROUTINE

    payload = {
        k: v
        for k, v in {
            "repo_count": getattr(args, "repo_count", None),
            "slug": getattr(args, "slug", None),
            "name": getattr(args, "name", None),
            "pitch": getattr(args, "pitch", None),
            "stack": getattr(args, "stack", None),
            "project_count": getattr(args, "project_count", None),
        }.items()
        if v is not None
    }

    # `publish` raises on an unknown type; the Literal on the args model means
    # that can only happen if the two drift apart, which is exactly when we
    # want to hear about it.
    await bus.publish(ctx.user_id, event, payload or None)

    if event == "done":
        n = payload.get("project_count", 0)
        return f"Reported. Onboarding complete — {n} project(s). The user's dashboard is live."
    return f"Reported {event}."
