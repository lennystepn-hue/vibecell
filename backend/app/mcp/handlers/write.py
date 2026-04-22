"""MCP write handlers — wired to backend services (Task 2.6)."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from app.mcp.auth import MCPContext
from app.mcp.handlers.read import _get_active_project, _resolve_project  # noqa: PLC2701
from app.services import secret as secret_svc

_VALID_STATUSES = {"idea", "building", "live", "paused", "shipped", "archived", "dead"}


# ---------------------------------------------------------------------------
# Secret helpers
# ---------------------------------------------------------------------------

def _detect_kind(value: str) -> str:
    v = value.strip()
    if v.startswith("op://"): return "op"
    if v.startswith("bw://"): return "bw"
    if v.startswith("ssh-agent://"): return "ssh_agent"
    if v.startswith("env://"): return "env_path"
    if v.startswith("keychain://"): return "keychain"
    return "inline_encrypted"


# ---------------------------------------------------------------------------
# Handler implementations
# ---------------------------------------------------------------------------

async def handle_switch(args, ctx: MCPContext) -> str:
    """Switch the active project to args.slug."""
    from sqlalchemy import select

    from app.models import Project
    from app.services.project import set_active_project

    project = (await ctx.db.execute(
        select(Project).where(
            Project.workspace_id == ctx.workspace_id,
            Project.slug == args.slug,
        )
    )).scalar_one_or_none()
    if not project:
        raise RuntimeError(f"Project {args.slug!r} not found in workspace")
    await set_active_project(
        ctx.db,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        project=project,
    )
    return json.dumps({"active_slug": args.slug})


def _auto_focus_from_summary(summary: str, cap: int = 280) -> str:
    """Derive a tidy current_focus snippet from a session summary.

    Takes the first sentence (up to the first period followed by space/newline/EOF),
    strips whitespace, and caps length. Falls back to truncating the whole summary
    if no sentence boundary is found.
    """
    s = (summary or "").strip()
    if not s:
        return ""
    # Find first ". " or "\n" — whichever comes first
    candidates = [i for i in (s.find(". "), s.find("\n")) if i > 0]
    cut = min(candidates) if candidates else -1
    head = s[:cut].strip() if cut > 0 else s
    if len(head) > cap:
        head = head[: cap - 1].rstrip() + "…"
    return head


async def handle_log_session(args, ctx: MCPContext) -> str:
    """Log a coding session and sync project context.

    Also updates the active project's current_focus (auto-derived from the
    summary unless args.current_focus is explicitly set) and next_step (if
    args.next_step is set). This keeps the session log and the project-level
    "what am I working on" view in sync without a second tool call.
    """
    from app.services import project_children as children_svc
    from app.services.session_svc import create_session

    project = await _get_active_project(ctx)
    now = datetime.now(UTC)
    session = await create_session(
        ctx.db,
        project=project,
        started_at=now,
        ended_at=now,
        summary=args.summary,
        files_touched=getattr(args, "files_touched", []) or [],
        commits=getattr(args, "commits", []) or [],
        next_step=getattr(args, "next_step", None),
        source="skill",
    )

    # Auto-sync project context so current_focus never goes stale between sessions.
    explicit_focus = getattr(args, "current_focus", None)
    new_focus = explicit_focus if explicit_focus is not None else _auto_focus_from_summary(args.summary)
    ctx_updates: dict[str, str] = {}
    if new_focus:
        ctx_updates["current_focus"] = new_focus
    next_step = getattr(args, "next_step", None)
    if next_step:
        ctx_updates["next_step"] = next_step
    if ctx_updates:
        await children_svc.upsert_context(ctx.db, project, **ctx_updates)

    return json.dumps({
        "id": session.id,
        "summary": session.summary,
        "next_step": session.next_step,
        "current_focus": ctx_updates.get("current_focus"),
    })


async def handle_update_context(args, ctx: MCPContext) -> str:
    """Patch the active project's context fields."""
    from app.services import project_children as children_svc

    project = await _get_active_project(ctx)
    fields = {
        k: v for k, v in {
            "current_focus": getattr(args, "current_focus", None),
            "next_step": getattr(args, "next_step", None),
            "user_wants": getattr(args, "user_wants", None),
            "open_questions": getattr(args, "open_questions", None),
            "known_issues": getattr(args, "known_issues", None),
            "blocked_by": getattr(args, "blocked_by", None),
        }.items()
        if v is not None
    }
    ctx_row = await children_svc.upsert_context(ctx.db, project, **fields)
    return json.dumps({
        "current_focus": ctx_row.current_focus,
        "next_step": ctx_row.next_step,
        "user_wants": ctx_row.user_wants,
        "open_questions": ctx_row.open_questions,
        "known_issues": ctx_row.known_issues,
        "blocked_by": ctx_row.blocked_by,
    })


async def handle_decision(args, ctx: MCPContext) -> str:
    """Record an ADR-lite decision on the active project."""
    from app.services.decision_svc import create_decision

    project = await _get_active_project(ctx)
    decision = await create_decision(
        ctx.db,
        project=project,
        title=args.title,
        decision=args.decision,
        context=getattr(args, "context", None),
        consequences=getattr(args, "consequences", None),
        reconsider_if=getattr(args, "reconsider_if", None),
    )
    return json.dumps({"id": decision.id, "title": decision.title})


async def handle_idea(args, ctx: MCPContext) -> str:
    """Capture an idea. Routes to workspace inbox if no project given."""
    from app.services.idea_svc import create_idea

    project_slug: str | None = getattr(args, "project", None)
    project_id: str | None = None

    if project_slug:
        project = await _resolve_project(args, ctx)
        project_id = project.id

    idea = await create_idea(
        ctx.db,
        workspace_id=ctx.workspace_id,
        body=args.body,
        project_id=project_id,
        source="skill",
    )
    return json.dumps({
        "id": idea.id,
        "body": idea.body,
        "project_id": idea.project_id,
    })


async def handle_note_append(args, ctx: MCPContext) -> str:
    """Append a markdown block to the active project's notes."""
    from app.services.note_svc import get_note, upsert_note

    project = await _get_active_project(ctx)
    existing = await get_note(ctx.db, project=project)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    new_block = f"\n\n---\n\n{timestamp}\n{args.markdown}"

    if existing and existing.markdown:
        updated_text = existing.markdown + new_block
    else:
        updated_text = args.markdown

    note = await upsert_note(ctx.db, project=project, markdown=updated_text)
    return json.dumps({"notes": note.markdown})


async def handle_ship(args, ctx: MCPContext) -> str:
    """Record a ship event (+ lifecycle row) for the active project."""
    from app.services.ship_svc import create_ship

    project = await _get_active_project(ctx)
    ship = await create_ship(
        ctx.db,
        project=project,
        version=getattr(args, "version", None),
        summary=getattr(args, "summary", None),
        changelog_md=getattr(args, "changelog_md", None),
    )
    return json.dumps({"id": ship.id, "version": ship.version})


async def handle_status(args, ctx: MCPContext) -> str:
    """Set the active project's status."""
    from app.services.project import update_project

    status: str = args.status
    if status not in _VALID_STATUSES:
        raise RuntimeError(
            f"Invalid status {status!r}. Must be one of: {', '.join(sorted(_VALID_STATUSES))}"
        )

    project = await _get_active_project(ctx)
    await update_project(ctx.db, project=project, status=status)
    return json.dumps({"slug": project.slug, "status": args.status})


async def handle_secret_set(args, ctx: MCPContext) -> str:
    """Upsert a secret for the project. Auto-detects kind from value prefix."""
    # Resolve project (args.project is a slug; falls back to active)
    from app.mcp.handlers.read import _get_active_project as _get_active  # noqa: PLC2701
    from sqlalchemy import select
    from app.models import Project
    from app.services.project import get_project

    project_slug: str | None = getattr(args, "project", None)
    if project_slug:
        project = await get_project(ctx.db, workspace_id=ctx.workspace_id, slug=project_slug)
    else:
        project = await _get_active(ctx)

    kind = _detect_kind(args.value)

    # Upsert: if label already exists, remove it first
    existing = await secret_svc.get_secret(ctx.db, project, args.label)
    if existing is not None:
        await secret_svc.remove_secret(ctx.db, project, args.label)

    ref = await secret_svc.add_secret(
        ctx.db,
        project,
        label=args.label,
        kind=kind,
        reference=args.value,
        workspace_id=ctx.workspace_id,
    )

    # ONLY return metadata — never the value
    return json.dumps({
        "ok": True,
        "label": ref.label,
        "kind": kind,
        "project": project.slug,
        "note": (
            "Value is encrypted at rest (inline) or stored as reference (op/bw/ssh)."
            if kind == "inline_encrypted"
            else "Reference stored; value never touches Vibecell."
        ),
    })


async def handle_secret_rm(args, ctx: MCPContext) -> str:
    """Remove a secret label from a project."""
    from app.services.project import get_project

    project_slug: str | None = getattr(args, "project", None)
    if project_slug:
        project = await get_project(ctx.db, workspace_id=ctx.workspace_id, slug=project_slug)
    else:
        project = await _get_active_project(ctx)

    await secret_svc.remove_secret(ctx.db, project, args.label)
    return json.dumps({"ok": True, "label": args.label, "project": project.slug})


# ---------------------------------------------------------------------------
# TODO handlers
# ---------------------------------------------------------------------------

def _todo_out(row) -> dict:
    return {
        "id": row.id,
        "batch": row.batch,
        "title": row.title,
        "body": row.body,
        "status": row.status,
        "position": row.position,
        "completed_by": row.completed_by,
        "completion_note": row.completion_note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


async def handle_todo_add(args, ctx: MCPContext) -> str:
    """Add a single todo to a project."""
    from app.services import todo_svc

    project = await _resolve_project(args, ctx)
    row = await todo_svc.create_todo(
        ctx.db,
        project=project,
        title=args.title,
        body=getattr(args, "body", None),
        batch=getattr(args, "batch", None),
    )
    return json.dumps(_todo_out(row))


async def handle_todo_batch_add(args, ctx: MCPContext) -> str:
    """Add many todos at once under one batch label."""
    from app.services import todo_svc

    project = await _resolve_project(args, ctx)
    items = [{"title": t} for t in args.titles]
    rows = await todo_svc.create_batch(
        ctx.db, project=project, batch=args.batch, items=items,
    )
    return json.dumps({
        "batch": args.batch,
        "count": len(rows),
        "todos": [_todo_out(r) for r in rows],
    })


async def handle_todo_start(args, ctx: MCPContext) -> str:
    """Mark a todo as in_progress — lights up the 'claude is on this' indicator."""
    from app.services import todo_svc

    project = await _resolve_project(args, ctx)
    row = await todo_svc.start_todo(ctx.db, project=project, todo_id=args.todo_id)
    return json.dumps(_todo_out(row))


async def handle_todo_complete(args, ctx: MCPContext) -> str:
    """Mark a todo as done (completed_by=claude). Pass completion_note describing what was built."""
    from app.services import todo_svc

    project = await _resolve_project(args, ctx)
    row = await todo_svc.complete_todo(
        ctx.db,
        project=project,
        todo_id=args.todo_id,
        completed_by="claude",
        completion_note=getattr(args, "completion_note", None),
    )
    return json.dumps(_todo_out(row))


async def handle_todo_match(args, ctx: MCPContext) -> str:
    """Fuzzy-match a description against open todos. Optionally auto-complete the best match."""
    from app.services import todo_svc

    project = await _resolve_project(args, ctx)
    best = await todo_svc.match_open_todo(
        ctx.db, project=project, description=args.description,
    )
    if best is None:
        return json.dumps({"matched": None, "note": "no open todo matched that description"})
    if getattr(args, "auto_complete", False):
        best = await todo_svc.complete_todo(
            ctx.db,
            project=project,
            todo_id=best.id,
            completed_by="claude",
            completion_note=args.description,
        )
    return json.dumps({"matched": _todo_out(best)})
