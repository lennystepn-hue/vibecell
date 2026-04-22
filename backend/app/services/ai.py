"""BYOK (Bring Your Own Key) AI service — server-side features that call
Anthropic using the user's own stored API key.

Key-resolution priority:
    1. Project-level secret labelled ANTHROPIC_API_KEY (inline_encrypted)
    2. Platform fallback env HANGAR_ANTHROPIC_API_KEY (operator pays)
    3. Error — user must set one

`op://` / `bw://` / `ssh-agent://` reference-kind secrets are skipped here
because the plaintext never reaches our server. Users with those kinds must
resolve locally (the CLI does this in the future).

Rate limiting, cost tracking, and key rotation live elsewhere.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Project
from app.services import secret as secret_svc

logger = logging.getLogger(__name__)

# Default model — user can pass `model=...` to override. Opus for planning,
# Sonnet for everything else. Keep Sonnet as default for latency + cost.
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
PLAN_MODEL = "claude-sonnet-4-5-20250929"
COPYWRITING_MODEL = "claude-sonnet-4-5-20250929"


class AIConfigError(Exception):
    """Raised when no usable API key is available for a project."""


async def _resolve_anthropic_key(
    db: AsyncSession, project: Project, *, workspace_id: str,
) -> tuple[str, str]:
    """Return (plaintext_key, source_label) or raise AIConfigError.

    source_label is one of "project-secret" | "platform-fallback" so
    callers can surface where the key came from (useful for billing UI).
    """
    # 1. Project-level inline_encrypted secret.
    try:
        row = await secret_svc.get_secret(db, project, "ANTHROPIC_API_KEY")
    except Exception:  # noqa: BLE001
        row = None

    if row is not None and row.kind == "inline_encrypted":
        try:
            value = await secret_svc.get_decrypted_value(
                db, project=project, label="ANTHROPIC_API_KEY", workspace_id=workspace_id,
            )
            return value, "project-secret"
        except Exception:  # noqa: BLE001
            logger.warning("AI key for %s failed to decrypt", project.slug, exc_info=True)
    elif row is not None:
        # reference kind — server can't use it directly.
        logger.info(
            "AI key for %s stored as %s reference; skipping (resolve locally).",
            project.slug, row.kind,
        )

    # 2. Platform fallback.
    fallback = (get_settings().anthropic_api_key or "").strip()
    if fallback:
        return fallback, "platform-fallback"

    raise AIConfigError(
        "No Anthropic API key available for this project. Store one via "
        "`vibecell.secret_set ANTHROPIC_API_KEY sk-ant-...` on the project, "
        "or ask the operator to set HANGAR_ANTHROPIC_API_KEY."
    )


async def _client_for_project(
    db: AsyncSession, project: Project, *, workspace_id: str,
) -> tuple[AsyncAnthropic, str]:
    key, source = await _resolve_anthropic_key(db, project, workspace_id=workspace_id)
    return AsyncAnthropic(api_key=key), source


async def complete(
    db: AsyncSession,
    *,
    project: Project,
    workspace_id: str,
    system: str,
    user_prompt: str,
    max_tokens: int = 2048,
    model: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Run a single-turn completion using the resolved API key.

    Returns (text, meta) where meta includes key_source + usage counts so the
    caller can show "generated with your key · 842 input / 310 output tokens".
    """
    client, source = await _client_for_project(db, project, workspace_id=workspace_id)
    resp = await client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    # Claude returns a list of content blocks; take the first text block.
    text = ""
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            text = block.text  # type: ignore[attr-defined]
            break

    meta = {
        "model": resp.model,
        "key_source": source,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }
    return text, meta


# ---------------------------------------------------------------------------
# Feature-specific wrappers
# ---------------------------------------------------------------------------

PLAN_SYSTEM = """\
You are the planning brain for Vibecell — "the operating system for vibecoders".

Given a project context and a goal, break the goal into 4-12 concrete, imperative
todo titles. Each title must:
- Start with a verb (Add, Wire, Migrate, Fix, Test, Deploy, …).
- Describe ONE independently-shippable unit of work.
- Be short (<= 80 chars).

Respond with ONLY valid JSON of this exact shape:
{
  "batch": "<kebab-case-name-summarising-the-goal>",
  "titles": ["<title 1>", "<title 2>", "..."]
}

No prose, no preamble, no code fences.
"""

LAUNCH_COPY_SYSTEM = """\
You write launch copy for indie hackers and vibecoders. Given a project pitch,
stack, and a recent ship event, produce crisp posts for the platforms requested.

Voice: confident, direct, no hype, no marketing fluff. No emojis unless the
platform demands it (X = 0-1 emoji max, LinkedIn = sparingly).

Respond with ONLY valid JSON of this exact shape:
{
  "posts": [
    {"platform": "twitter_x", "text": "..."},
    {"platform": "linkedin", "text": "..."},
    {"platform": "indiehackers", "text": "..."},
    {"platform": "product_hunt", "text": "..."}
  ]
}

No prose, no preamble. Include ONLY the platforms the user asked for.
Character limits to respect: twitter_x <= 280, linkedin <= 1300, indiehackers
unrestricted, product_hunt tagline <= 60 chars + body.
"""

RETRO_SYSTEM = """\
You write one-page retrospectives for indie hackers. Given sessions + decisions +
ships since the last retro, produce a tight markdown retro with three sections:

# What worked
- Concrete wins backed by session evidence.

# What didn't
- Friction, dropped threads, rework. Honest and specific.

# Next time
- 3-5 actionable rules for the next sprint. Not platitudes.

Max ~400 words. Use bullet points. No filler.
"""

BRIEF_SYSTEM = """\
You generate the "Where the fuck was I?" morning brief for a vibecoder returning
to a project. This is the FIRST thing they see when they open their dashboard.

TONE: funny, warm, slightly irreverent. Like a best friend roasting them gently
about the state of their code. German-English code-switching is welcome (the
audience is a Denglisch-speaking indie hacker). Light swearing ("der fucking
Stripe webhook") is fine. No corpo voice. No emojis unless one really lands.

STRUCTURE (120-180 words, flowing prose, no headings):
1. Open with a beat of personality — tease them about where they left off
   ("Moin. Also du hast dich gestern 23:41 vom auth-refactor verabschiedet
    mitten im stripe-hook — klassisch.").
2. One sentence: what they actually shipped yesterday (concrete).
3. One sentence: exactly where to pick up (file + line or high-level).
4. A line: what's blocking or still open (if anything).
5. A confidence-building closer ("du bist 2 commits vom demo entfernt, geh ran").

END with a single concrete action in *italics* like *"Kaffee, dann auth.py:47."*
or *"Open the Stripe dashboard and grep for test_webhook."*.

NEVER be motivational-poster cringe. Never say "you got this" or "let's crush
it". Be the friend who actually knows the codebase.
"""


async def plan_todos(
    db: AsyncSession,
    *,
    project: Project,
    workspace_id: str,
    goal: str,
    context_brief: str,
) -> tuple[str, list[str], dict[str, Any]]:
    """Generate (batch_name, titles, meta) for a goal."""
    user_prompt = (
        f"PROJECT CONTEXT:\n{context_brief}\n\n"
        f"GOAL:\n{goal.strip()}\n\n"
        "Return JSON only."
    )
    text, meta = await complete(
        db,
        project=project,
        workspace_id=workspace_id,
        system=PLAN_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=1024,
        model=PLAN_MODEL,
    )
    parsed = _safe_json_loads(text)
    batch = str(parsed.get("batch") or "plan").strip() or "plan"
    titles = [str(t).strip() for t in parsed.get("titles") or [] if str(t).strip()]
    return batch, titles, meta


async def launch_copy(
    db: AsyncSession,
    *,
    project: Project,
    workspace_id: str,
    ship_context: str,
    platforms: list[str],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Generate posts for the requested platforms (twitter_x/linkedin/…)."""
    user_prompt = (
        f"SHIP CONTEXT:\n{ship_context}\n\n"
        f"PLATFORMS REQUESTED: {', '.join(platforms)}\n\n"
        "Return JSON only."
    )
    text, meta = await complete(
        db,
        project=project,
        workspace_id=workspace_id,
        system=LAUNCH_COPY_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=2048,
        model=COPYWRITING_MODEL,
    )
    parsed = _safe_json_loads(text)
    posts_raw = parsed.get("posts") or []
    posts: list[dict[str, str]] = []
    for p in posts_raw:
        platform = str(p.get("platform") or "").strip()
        text_block = str(p.get("text") or "").strip()
        if platform and text_block:
            posts.append({"platform": platform, "text": text_block})
    return posts, meta


async def retro(
    db: AsyncSession,
    *,
    project: Project,
    workspace_id: str,
    events_summary: str,
) -> tuple[str, dict[str, Any]]:
    user_prompt = (
        f"PROJECT: {project.name} ({project.slug})\n\n"
        f"EVENTS SINCE LAST RETRO:\n{events_summary}\n\n"
        "Write the retro in markdown."
    )
    text, meta = await complete(
        db,
        project=project,
        workspace_id=workspace_id,
        system=RETRO_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=2048,
    )
    return text.strip(), meta


async def resume_brief(
    db: AsyncSession,
    *,
    project: Project,
    workspace_id: str,
    context_blob: str,
) -> tuple[str, dict[str, Any]]:
    user_prompt = (
        f"PROJECT: {project.name} ({project.slug})\n\n"
        f"CONTEXT:\n{context_blob}\n\n"
        "Write the brief."
    )
    text, meta = await complete(
        db,
        project=project,
        workspace_id=workspace_id,
        system=BRIEF_SYSTEM,
        user_prompt=user_prompt,
        max_tokens=512,
    )
    return text.strip(), meta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_json_loads(text: str) -> dict[str, Any]:
    """Best-effort JSON parse, stripping code fences the model sometimes adds."""
    s = text.strip()
    # Strip ```json ... ``` or ``` ... ```
    if s.startswith("```"):
        # drop first line (```json) and last ```
        lines = s.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        logger.warning("ai_svc: model returned non-JSON: %s", s[:200])
        return {}
