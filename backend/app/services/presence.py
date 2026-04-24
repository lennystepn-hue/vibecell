"""Ephemeral MCP presence — which project Claude is live on, right now.

Backed by Redis with short TTLs so there's no DB write on every tool call and
keys disappear automatically when Claude goes quiet.

Keyspace:
    vc:presence:{workspace_id}:{project_slug}  -> JSON blob { tool, at, session_id }
                                                   TTL = PRESENCE_TTL_SECONDS

Writers:  mcp.server._dispatch_tool_call calls mark_live() on every tool call.
Readers:  GET /api/v1/workspaces/me/presence scans the set and returns the live projects.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.core.redis import get_redis

PRESENCE_TTL_SECONDS = 120  # project counts as "live" for 2 minutes after last tool call
INDEX_KEY_TMPL = "vc:presence:index:{workspace_id}"
ENTRY_KEY_TMPL = "vc:presence:{workspace_id}:{project_slug}"


def _entry_key(workspace_id: str, project_slug: str) -> str:
    return ENTRY_KEY_TMPL.format(workspace_id=workspace_id, project_slug=project_slug)


def _index_key(workspace_id: str) -> str:
    return INDEX_KEY_TMPL.format(workspace_id=workspace_id)


async def mark_live(
    *,
    workspace_id: str,
    project_slug: str,
    tool_name: str,
    session_id: str | None = None,
) -> None:
    """Record that Claude just ran tool_name against project_slug in workspace_id.

    Semantic: Claude can only be "live" on ONE project at a time from the user's
    perspective — when a new tool-call touches project B we clear every other
    entry for this workspace. Without this, the 120s TTL left stale dots on
    previously-touched projects and the sidebar showed pulsing greens on
    unrelated rows while Claude was only actually working on one.
    """
    r = await get_redis()
    now_iso = datetime.now(UTC).isoformat()
    payload = json.dumps({
        "tool": tool_name,
        "at": now_iso,
        "session_id": session_id or "",
    })
    key = _entry_key(workspace_id, project_slug)
    idx = _index_key(workspace_id)

    # Clear every other project's presence entry so only the just-touched slug
    # renders as live. Do this BEFORE the pipeline write so there's no race
    # where two entries are briefly live together.
    existing_slugs = await r.smembers(idx)
    stale_slugs = [s for s in existing_slugs if s != project_slug]
    if stale_slugs:
        pipe = r.pipeline()
        for s in stale_slugs:
            pipe.delete(_entry_key(workspace_id, s))
        pipe.srem(idx, *stale_slugs)
        await pipe.execute()

    pipe = r.pipeline()
    pipe.set(key, payload, ex=PRESENCE_TTL_SECONDS)
    pipe.sadd(idx, project_slug)
    pipe.expire(idx, PRESENCE_TTL_SECONDS * 4)  # index re-bumps on every ping
    await pipe.execute()


async def get_live(workspace_id: str) -> list[dict[str, Any]]:
    """Return live presence entries for a workspace.

    Shape: [{ slug, tool, at, age_seconds }]. Stale index entries are garbage-
    collected lazily whenever we find one whose entry key has expired.
    """
    r = await get_redis()
    idx = _index_key(workspace_id)
    slugs = await r.smembers(idx)
    if not slugs:
        return []

    now = datetime.now(UTC)
    out: list[dict[str, Any]] = []
    stale: list[str] = []
    for slug in slugs:
        raw = await r.get(_entry_key(workspace_id, slug))
        if raw is None:
            stale.append(slug)
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            stale.append(slug)
            continue
        try:
            age = (now - datetime.fromisoformat(data["at"])).total_seconds()
        except (KeyError, ValueError):
            age = 0.0
        out.append({
            "slug": slug,
            "tool": data.get("tool"),
            "at": data.get("at"),
            "age_seconds": int(age),
        })
    if stale:
        await r.srem(idx, *stale)
    out.sort(key=lambda e: e["age_seconds"])
    return out


async def clear(workspace_id: str, project_slug: str) -> None:
    """Force-clear a presence entry (e.g. on project delete)."""
    r = await get_redis()
    pipe = r.pipeline()
    pipe.delete(_entry_key(workspace_id, project_slug))
    pipe.srem(_index_key(workspace_id), project_slug)
    await pipe.execute()
