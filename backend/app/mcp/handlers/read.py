"""MCP read handlers — wired to backend services (Task 2.5)."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.mcp.auth import MCPContext
from app.mcp.handlers.render import render_claude_md, render_handover
from app.models import ActiveProject, Project
from app.models.project import (
    ProjectLink,
)
from app.schemas.project import (
    CommandOut,
    ContextOut,
    EnvironmentOut,
    InfraOut,
    LinkOut,
    ProjectListItem,
    ProjectOut,
    RepoOut,
    StackOut,
)
from app.schemas.tag import TagOut
from app.services import project_children as children_svc
from app.services import secret as secret_svc
from app.services.activity import fetch_activity
from app.services.project import get_project, list_projects
from app.services.search import union_search

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _project_to_out(project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        slug=project.slug,
        name=project.name,
        emoji=project.emoji,
        color=project.color,
        pitch=project.pitch,
        status=project.status,
        is_public=project.is_public,
        archived_at=project.archived_at.isoformat() if project.archived_at else None,
        group_id=project.group_id,
        position=project.position,
    )


async def _get_active_project(ctx: MCPContext) -> Project:
    """Resolve the active project for (workspace_id, user_id) or raise RuntimeError."""
    active_row = (await ctx.db.execute(
        select(ActiveProject).where(
            ActiveProject.workspace_id == ctx.workspace_id,
        )
    )).scalar_one_or_none()
    if active_row is None:
        raise RuntimeError("No active project — call vibecell.switch(slug) first")
    project = await get_project(
        ctx.db, workspace_id=ctx.workspace_id, slug=(
            await ctx.db.execute(
                select(Project.slug).where(Project.id == active_row.project_id)
            )
        ).scalar_one()
    )
    return project


async def _resolve_project(args: Any, ctx: MCPContext) -> Project:
    """Return the project for args.slug or fall back to the active project."""
    slug: str | None = getattr(args, "slug", None)
    if slug:
        return await get_project(ctx.db, workspace_id=ctx.workspace_id, slug=slug)
    return await _get_active_project(ctx)


async def _build_full_dict(project: Project, db: Any) -> dict[str, Any]:
    """Compose the full project aggregate dict (matches ProjectFullOut shape)."""
    ctx_row = await children_svc.get_context(db, project)
    infra_row = await children_svc.get_infra(db, project)
    repos = await children_svc.list_repos(db, project)
    envs = await children_svc.list_environments(db, project)
    links = await children_svc.list_links(db, project)
    commands = await children_svc.list_commands(db, project)
    stack = await children_svc.list_stack(db, project)
    tags = await children_svc.list_tags(db, project)

    base = _project_to_out(project).model_dump(mode="json")
    base["context"] = ContextOut.model_validate(ctx_row).model_dump(mode="json") if ctx_row else None
    base["infra"] = InfraOut.model_validate(infra_row).model_dump(mode="json") if infra_row else None
    base["repos"] = [RepoOut.model_validate(r).model_dump(mode="json") for r in repos]
    base["environments"] = [EnvironmentOut.model_validate(e).model_dump(mode="json") for e in envs]
    base["links"] = [LinkOut.model_validate(lnk).model_dump(mode="json") for lnk in links]
    base["commands"] = [CommandOut.model_validate(c).model_dump(mode="json") for c in commands]
    base["stack"] = [
        StackOut(stack_item_slug=si.slug, name=si.name, kind=si.kind, role=ps.role).model_dump(mode="json")
        for si, ps in stack
    ]
    base["tags"] = [TagOut.model_validate(t).model_dump(mode="json") for t in tags]

    # env_status: derived hint so Claude can decide whether to scan/refresh.
    # needs_initial_scan = project has no stack AND no infra AND no fingerprint yet.
    # local_path / last_scanned pulled from env_fingerprint for convenience.
    fingerprint = (ctx_row.env_fingerprint if ctx_row else {}) or {}
    has_fingerprint = bool(fingerprint.get("files"))
    naked = (not stack) and (infra_row is None)
    base["env_status"] = {
        "needs_initial_scan": (naked and not has_fingerprint),
        "has_fingerprint": has_fingerprint,
        "last_scanned": fingerprint.get("scanned_at"),
        "local_path": fingerprint.get("local_path") or (repos[0].local_path if repos else None),
        "tracked_files": sorted(list(fingerprint.get("files", {}).keys())) if has_fingerprint else [],
    }
    return base


# ---------------------------------------------------------------------------
# Handler implementations
# ---------------------------------------------------------------------------

async def handle_ping(args: Any, ctx: MCPContext) -> str:
    """Health check — returns ok, version, active_slug."""
    active_row = (await ctx.db.execute(
        select(ActiveProject).where(
            ActiveProject.workspace_id == ctx.workspace_id,
        )
    )).scalar_one_or_none()

    active_slug: str | None = None
    if active_row is not None:
        active_slug = (await ctx.db.execute(
            select(Project.slug).where(Project.id == active_row.project_id)
        )).scalar_one_or_none()

    return json.dumps({"ok": True, "version": "0.1.0", "active_slug": active_slug})


async def handle_active(args: Any, ctx: MCPContext) -> str:
    """Return the full aggregate of the currently-active project."""
    project = await _get_active_project(ctx)
    full = await _build_full_dict(project, ctx.db)
    return json.dumps(full)


async def _github_url_map(db, projects) -> dict[str, str]:
    """Return {project_id: github_url} for the given projects (from kind='github' ProjectLink)."""
    if not projects:
        return {}
    links = (await db.execute(
        select(ProjectLink).where(
            ProjectLink.project_id.in_([p.id for p in projects]),
            ProjectLink.kind == "github",
        )
    )).scalars().all()
    out: dict[str, str] = {}
    for link in links:
        out.setdefault(link.project_id, link.url)
    return out


async def handle_list(args: Any, ctx: MCPContext) -> str:
    """List projects in the workspace with optional status/tag/q filters."""
    items, _ = await list_projects(
        ctx.db,
        workspace_id=ctx.workspace_id,
        status=getattr(args, "status", None),
        tag=getattr(args, "tag", None),
        q=getattr(args, "q", None),
        limit=200,
    )
    github_urls = await _github_url_map(ctx.db, items)
    out = []
    for p in items:
        data = ProjectListItem.model_validate(p).model_dump(mode="json")
        data["github_url"] = github_urls.get(p.id)
        out.append(data)
    return json.dumps(out)


async def handle_get(args: Any, ctx: MCPContext) -> str:
    """Return the full aggregate for a project identified by args.slug."""
    slug: str = args.slug  # required by SlugRequired schema
    project = await get_project(ctx.db, workspace_id=ctx.workspace_id, slug=slug)
    full = await _build_full_dict(project, ctx.db)
    return json.dumps(full)


async def handle_brief(args: Any, ctx: MCPContext) -> str:
    """Resurrection brief for active or named project (prose text, not JSON)."""
    project = await _resolve_project(args, ctx)
    full = await _build_full_dict(project, ctx.db)
    return render_handover(full)


async def handle_search(args: Any, ctx: MCPContext) -> str:
    """Federated FTS across the workspace."""
    q: str = args.q
    limit: int = getattr(args, "limit", 50)
    hits = await union_search(
        ctx.db,
        workspace_id=ctx.workspace_id,
        query=q,
        limit=limit,
    )
    return json.dumps({"results": [h.to_dict() for h in hits]})


async def handle_recent(args: Any, ctx: MCPContext) -> str:
    """Return the top-n projects by position (proxy for recently-touched)."""
    n: int = getattr(args, "n", 5)
    items, _ = await list_projects(
        ctx.db,
        workspace_id=ctx.workspace_id,
        limit=max(n, 1),
    )
    trimmed = items[:n]
    github_urls = await _github_url_map(ctx.db, trimmed)
    out = []
    for p in trimmed:
        data = ProjectListItem.model_validate(p).model_dump(mode="json")
        data["github_url"] = github_urls.get(p.id)
        out.append(data)
    return json.dumps(out)


async def handle_claude_md(args: Any, ctx: MCPContext) -> str:
    """Generate a CLAUDE.md-ready markdown brief for active or named project."""
    project = await _resolve_project(args, ctx)
    full = await _build_full_dict(project, ctx.db)
    return render_claude_md(full)


async def handle_handover(args: Any, ctx: MCPContext) -> str:
    """Return a longer onboarding/resurrection brief as prose."""
    project = await _resolve_project(args, ctx)
    full = await _build_full_dict(project, ctx.db)
    return render_handover(full)


async def handle_activity(args: Any, ctx: MCPContext) -> str:
    """Unified activity feed for a project (sessions, decisions, ideas, ships, lifecycle, tool calls)."""
    project = await _resolve_project(args, ctx)
    limit: int = getattr(args, "limit", 50)
    events = await fetch_activity(ctx.db, project=project, limit=limit)
    return json.dumps(events)


async def handle_todo_list(args: Any, ctx: MCPContext) -> str:
    """List a project's todos (open + in_progress by default)."""
    from app.services import todo_svc

    project = await _resolve_project(args, ctx)
    include_done = getattr(args, "include_done", False)
    rows = await todo_svc.list_todos(
        ctx.db, project=project, include_done=include_done,
    )
    out = [
        {
            "id": r.id,
            "batch": r.batch,
            "title": r.title,
            "body": r.body,
            "status": r.status,
            "position": r.position,
            "completed_by": r.completed_by,
            "completion_note": r.completion_note,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in rows
    ]
    return json.dumps(out)


def _mask_secret(value: str | None, kind: str) -> str:
    """Return the reference path for non-inline kinds; mask inline encrypted values."""
    if kind != "inline_encrypted" and value:
        return value
    return "******"


async def handle_secret_list(args: Any, ctx: MCPContext) -> str:
    """List labels + kinds + masked references for a project's secrets. Never returns values."""
    project_slug: str | None = getattr(args, "project", None)
    if project_slug:
        project = await get_project(ctx.db, workspace_id=ctx.workspace_id, slug=project_slug)
    else:
        project = await _get_active_project(ctx)

    rows = await secret_svc.list_secrets(ctx.db, project=project)
    out = [
        {
            "label": r.label,
            "kind": r.kind,
            "reference": _mask_secret(r.reference, r.kind),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
        }
        for r in rows
    ]
    return json.dumps(out)


async def handle_secret_get_value(args: Any, ctx: MCPContext) -> str:
    """Retrieve plaintext value. For inline_encrypted: decrypts. For references (op/bw/ssh): returns path."""
    project_slug: str | None = getattr(args, "project", None)
    if project_slug:
        project = await get_project(ctx.db, workspace_id=ctx.workspace_id, slug=project_slug)
    else:
        project = await _get_active_project(ctx)

    row = await secret_svc.get_secret(ctx.db, project=project, label=args.label)
    if row is None:
        return json.dumps({"error": "not_found", "label": args.label})

    if row.kind == "inline_encrypted":
        value = await secret_svc.get_decrypted_value(
            ctx.db, project=project, label=args.label, workspace_id=ctx.workspace_id,
        )
        return json.dumps({
            "label": row.label,
            "kind": row.kind,
            "value": value,
            "note": "PLAINTEXT — do not echo in user-visible chat. Use silently in tool calls/commands.",
        })

    # Reference kinds — return the path, caller must resolve locally.
    # Still mark the secret as used so the UI "@LABEL used Xm ago" indicator updates.
    await secret_svc.touch_last_used(ctx.db, project=project, label=args.label)
    return json.dumps({
        "label": row.label,
        "kind": row.kind,
        "reference": row.reference,
        "note": f"This is a {row.kind} reference. The value lives in the user's {row.kind} vault — not retrievable server-side. Use the path with `op read` / `bw get` / etc. on the user's machine.",
    })


# ---------------------------------------------------------------------------
# Environment drift — read-only check: did manifests change since last scan?
# ---------------------------------------------------------------------------

async def handle_check_env_drift(args: Any, ctx: MCPContext) -> str:
    """Compare fresh manifest contents against the stored fingerprint.

    Pure read: no DB writes. Use this when you want to know 'did my repo's
    env change?' without triggering a re-enrichment. If you want to REFRESH
    the fingerprint + stack/infra when drift is detected, call vibecell_sync_repo
    instead (it handles both cases).

    Returns:
        {
          "drifted": bool,
          "never_scanned": bool,
          "changed_files": [...],
          "new_files": [...],
          "removed_files": [...],
          "last_scanned": iso | null
        }
    """
    from app.services.env_fingerprint import compute_drift

    project = await _resolve_project(args, ctx)
    ctx_row = await children_svc.get_context(ctx.db, project)
    stored_fp = (ctx_row.env_fingerprint if ctx_row else {}) or {}

    manifests: dict[str, str] = dict(getattr(args, "manifests", {}) or {})
    drift = compute_drift(stored_fp, manifests)

    return json.dumps({
        "drifted": drift.drifted,
        "never_scanned": drift.never_scanned,
        "changed_files": drift.changed_files,
        "new_files": drift.new_files,
        "removed_files": drift.removed_files,
        "last_scanned": drift.last_scanned,
        "local_path": stored_fp.get("local_path"),
    })


# ---------------------------------------------------------------------------
# Audit — single call Claude runs at session start to see what's out of sync.
# Answers: "what cards on this project's dashboard are stale / missing?"
# ---------------------------------------------------------------------------

async def handle_audit(args: Any, ctx: MCPContext) -> str:
    """Return a structured audit of what's stale or unsynced on the project.

    Designed to be called on session start so Claude can proactively catch
    gaps — decisions not recorded, ships not tagged, context fields empty,
    env never scanned, etc. Every field is a concrete hint Claude can act on.

    Shape:
        {
          "project_slug": str,
          "gaps": [{"kind": "…", "message": "…", "action": "…"}],
          "stats": {
            "sessions_7d": int,
            "decisions_total": int,
            "ships_total": int,
            "todos_open": int,
            "ideas_open": int,
          },
          "last_activity": iso | null
        }
    """
    from datetime import UTC, datetime, timedelta

    from app.models import Decision, Idea, Ship
    from app.models import Session as SessionRow
    from app.models.project import ProjectCommand, ProjectEnvironment
    from app.models.todo import ProjectTodo

    project = await _resolve_project(args, ctx)
    ctx_row = await children_svc.get_context(ctx.db, project)
    stack = await children_svc.list_stack(ctx.db, project)
    infra_row = await children_svc.get_infra(ctx.db, project)

    # Counts
    now = datetime.now(UTC)
    seven_ago = now - timedelta(days=7)

    sessions_7d_q = await ctx.db.execute(
        select(SessionRow).where(
            SessionRow.project_id == project.id,
            SessionRow.started_at >= seven_ago,
        )
    )
    sessions_7d = len(sessions_7d_q.scalars().all())

    latest_session = (await ctx.db.execute(
        select(SessionRow).where(SessionRow.project_id == project.id)
        .order_by(SessionRow.started_at.desc()).limit(1)
    )).scalar_one_or_none()

    decisions = (await ctx.db.execute(
        select(Decision).where(Decision.project_id == project.id)
    )).scalars().all()
    ships = (await ctx.db.execute(
        select(Ship).where(Ship.project_id == project.id)
    )).scalars().all()
    todos_open = (await ctx.db.execute(
        select(ProjectTodo).where(
            ProjectTodo.project_id == project.id,
            ProjectTodo.status.in_(["open", "in_progress"]),
        )
    )).scalars().all()
    ideas = (await ctx.db.execute(
        select(Idea).where(Idea.project_id == project.id)
    )).scalars().all()
    environments = (await ctx.db.execute(
        select(ProjectEnvironment).where(ProjectEnvironment.project_id == project.id)
    )).scalars().all()
    commands = (await ctx.db.execute(
        select(ProjectCommand).where(ProjectCommand.project_id == project.id)
    )).scalars().all()

    # Gap detection
    gaps: list[dict[str, str]] = []

    if not project.pitch or len(project.pitch or "") < 20:
        gaps.append({
            "kind": "pitch_missing",
            "message": "Project has no pitch or it's too short.",
            "action": "Ask the user for a 1-sentence pitch and call vibecell_update_context or create_project/sync_repo.",
        })

    if not stack:
        gaps.append({
            "kind": "stack_empty",
            "message": "No stack items. User can't see what this project is made of.",
            "action": "Read local manifests + call vibecell_sync_repo, or ask the user about the stack.",
        })

    if infra_row is None or not any([infra_row.db_host, infra_row.server_alias, infra_row.cdn]):
        gaps.append({
            "kind": "infra_sparse",
            "message": "Infra card is empty (no db_host, server, or cdn).",
            "action": "Call vibecell_sync_repo to infer from manifests, or ask user about hosting.",
        })

    if not environments:
        gaps.append({
            "kind": "no_environments",
            "message": "No environments recorded (local/prod URLs).",
            "action": "Call vibecell_add_environment with at least the prod URL if the project has one.",
        })

    if not commands:
        gaps.append({
            "kind": "no_commands",
            "message": "No runnable commands (dev/build/test).",
            "action": "Read package.json or Makefile and add via vibecell_add_command.",
        })

    fp = (ctx_row.env_fingerprint if ctx_row else {}) or {}
    if not fp.get("files"):
        gaps.append({
            "kind": "never_scanned",
            "message": "Repo never scanned — env drift detection is off until a baseline exists.",
            "action": "Call vibecell_sync_repo with the local manifests to establish a fingerprint.",
        })

    if ctx_row is None or not ctx_row.current_focus:
        gaps.append({
            "kind": "no_current_focus",
            "message": "current_focus is empty — future sessions can't resume.",
            "action": "Call vibecell_update_context with a 1-sentence focus.",
        })

    if ctx_row is None or not ctx_row.next_step:
        gaps.append({
            "kind": "no_next_step",
            "message": "next_step is empty.",
            "action": "Call vibecell_update_context with a concrete next step.",
        })

    if latest_session is not None and latest_session.started_at is not None:
        age_h = (now - latest_session.started_at).total_seconds() / 3600
        if age_h > 48:
            gaps.append({
                "kind": "stale_sessions",
                "message": f"Last session was {int(age_h)}h ago. Project might be stale.",
                "action": "Confirm with user if still active; consider status change via vibecell_status.",
            })
    elif latest_session is None:
        gaps.append({
            "kind": "no_sessions_yet",
            "message": "No sessions logged. The dashboard will look empty.",
            "action": "Log the first session via vibecell_log_session after any work.",
        })

    return json.dumps({
        "project_slug": project.slug,
        "gaps": gaps,
        "stats": {
            "sessions_7d": sessions_7d,
            "decisions_total": len(decisions),
            "ships_total": len(ships),
            "todos_open": len(todos_open),
            "ideas_open": len(ideas),
            "environments_count": len(environments),
            "commands_count": len(commands),
        },
        "last_activity": latest_session.started_at.isoformat() if latest_session and latest_session.started_at else None,
    })
