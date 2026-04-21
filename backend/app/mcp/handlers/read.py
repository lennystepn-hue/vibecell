"""MCP read handlers — wired to backend services (Task 2.5)."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.mcp.auth import MCPContext
from app.mcp.handlers.render import render_claude_md, render_handover
from app.models import ActiveProject, Project
from app.models.project import (
    ProjectCommand,
    ProjectContext,
    ProjectEnvironment,
    ProjectInfra,
    ProjectLink,
    ProjectRepo,
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
    return base


# ---------------------------------------------------------------------------
# Handler implementations
# ---------------------------------------------------------------------------

async def handle_ping(args: Any, ctx: MCPContext) -> str:  # noqa: ARG001
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


async def handle_active(args: Any, ctx: MCPContext) -> str:  # noqa: ARG001
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
        }
        for r in rows
    ]
    return json.dumps(out)
