"""Unified activity feed per project — aggregates events across tables."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.audit import McpAuditLog
from app.models import Decision, Idea, LifecycleEvent, Note, Project, ProjectTodo, Session, Ship


async def fetch_activity(
    db: AsyncSession, *, project: Project, limit: int = 100,
) -> list[dict[str, Any]]:
    """Return events for a project in reverse-chronological order."""
    events: list[dict[str, Any]] = []

    # Sessions
    sess_rows = (await db.execute(
        select(Session).where(Session.project_id == project.id)
        .order_by(Session.started_at.desc()).limit(20)
    )).scalars().all()
    for s in sess_rows:
        commits = s.commits if isinstance(s.commits, list) else []
        events.append({
            "type": "session",
            "at": s.started_at.isoformat() if s.started_at else None,
            "title": (s.summary or "")[:160],
            "body": s.summary,
            "meta": {
                "id": s.id,
                "next_step": s.next_step,
                "files_touched": s.files_touched or [],
                "commit_count": len(commits),
                "commits": commits[:5],
            },
        })

    # Decisions
    dec_rows = (await db.execute(
        select(Decision).where(Decision.project_id == project.id)
        .order_by(Decision.created_at.desc()).limit(30)
    )).scalars().all()
    for d in dec_rows:
        events.append({
            "type": "decision",
            "at": d.created_at.isoformat() if d.created_at else None,
            "title": d.title,
            "body": d.decision,
            "meta": {
                "id": d.id,
                "consequences": d.consequences,
                "reconsider_if": d.reconsider_if,
            },
        })

    # Ideas (project-scoped) — Idea uses captured_at, not created_at
    try:
        idea_rows = (await db.execute(
            select(Idea).where(Idea.project_id == project.id)
            .order_by(Idea.captured_at.desc()).limit(20)
        )).scalars().all()
        for i in idea_rows:
            events.append({
                "type": "idea",
                "at": i.captured_at.isoformat() if i.captured_at else None,
                "title": (i.body or "")[:160],
                "body": i.body,
                "meta": {"status": i.status},
            })
    except Exception:
        pass

    # Ships
    ship_rows = (await db.execute(
        select(Ship).where(Ship.project_id == project.id)
        .order_by(Ship.shipped_at.desc()).limit(20)
    )).scalars().all()
    for sh in ship_rows:
        events.append({
            "type": "ship",
            "at": sh.shipped_at.isoformat() if sh.shipped_at else None,
            "title": f"Shipped {sh.version or ''}".strip(),
            "body": sh.summary,
            "meta": {"version": sh.version},
        })

    # Note (singleton — emit one event if the note has been updated)
    note_row = (await db.execute(
        select(Note).where(Note.project_id == project.id)
    )).scalar_one_or_none()
    if note_row and note_row.markdown:
        events.append({
            "type": "note",
            "at": note_row.updated_at.isoformat() if note_row.updated_at else None,
            "title": "Notes updated",
            "body": None,
            "meta": {},
        })

    # TODOs — completed items show as "checked" rows, started-but-not-done
    # appear as "in progress". Open, untouched todos do NOT show (they'd spam
    # the feed on batch creation). Sort by completed_at when present, else
    # started_at.
    todo_rows = (await db.execute(
        select(ProjectTodo)
        .where(ProjectTodo.project_id == project.id)
        .where(ProjectTodo.status.in_(["in_progress", "done"]))
        .order_by(ProjectTodo.completed_at.desc().nullslast(),
                  ProjectTodo.started_at.desc().nullslast())
        .limit(40)
    )).scalars().all()
    for t in todo_rows:
        at = t.completed_at or t.started_at
        title = f"{'✓' if t.status == 'done' else '◉'} {t.title}"
        events.append({
            "type": "todo",
            "at": at.isoformat() if at else None,
            "title": title,
            "body": t.completion_note,
            "meta": {
                "id": t.id,
                "status": t.status,
                "batch": t.batch,
                "completed_by": t.completed_by,
            },
        })

    # Lifecycle events
    life_rows = (await db.execute(
        select(LifecycleEvent).where(LifecycleEvent.project_id == project.id)
        .order_by(LifecycleEvent.at.desc()).limit(30)
    )).scalars().all()
    for le in life_rows:
        events.append({
            "type": "lifecycle",
            "at": le.at.isoformat() if le.at else None,
            "title": f"Lifecycle: {le.kind}",
            "body": None,
            "meta": le.detail or {},
        })

    # MCP tool calls (workspace-scoped)
    tool_rows = (await db.execute(
        select(McpAuditLog)
        .where(McpAuditLog.workspace_id == project.workspace_id)
        .order_by(McpAuditLog.called_at.desc()).limit(limit)
    )).scalars().all()
    for tc in tool_rows:
        events.append({
            "type": "tool_call",
            "at": tc.called_at.isoformat() if tc.called_at else None,
            "title": tc.tool_name,
            "body": None,
            "meta": {"duration_ms": tc.duration_ms, "status": tc.status, "client_id": tc.client_id},
        })

    # Sort descending by at, push None-at entries to the end
    events.sort(key=lambda e: e["at"] or "", reverse=True)
    return events[:limit]
