"""Projects CRUD + active-project switch."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, ProjectContext, require_auth, require_project
from app.models import Project
from app.schemas.project import (
    CommandOut,
    ContextOut,
    EnvironmentOut,
    InfraOut,
    LinkOut,
    ProjectCreate,
    ProjectFullOut,
    ProjectListItem,
    ProjectListPage,
    ProjectOut,
    ProjectUpdate,
    RepoOut,
    StackOut,
    TagOut,
)
from app.services import project_children as children_svc
from app.services.project import (
    create_project,
    delete_project,
    list_projects,
    set_active_project,
    update_project,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _to_out(project: Project) -> ProjectOut:
    # created_at / updated_at come from TimestampMixin and were silently
    # dropped here — leaving the telemetry rail's "created" row stuck on "—"
    # forever. Include them as ISO strings so the frontend formats them.
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
        created_at=project.created_at.isoformat() if project.created_at else None,
        updated_at=project.updated_at.isoformat() if project.updated_at else None,
        group_id=project.group_id,
        position=project.position,
    )


@router.get("", response_model=ProjectListPage)
async def list_(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    tag: str | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ProjectListPage:
    items, next_cursor = await list_projects(
        db,
        workspace_id=auth.active_workspace_id,
        status=status_filter,
        tag=tag,
        q=q,
        cursor=cursor,
        limit=limit,
    )
    # Decorate each with github_url (first github-kind ProjectLink)
    from app.models import ProjectLink
    github_urls: dict[str, str] = {}
    if items:
        links = (await db.execute(
            select(ProjectLink).where(
                ProjectLink.project_id.in_([p.id for p in items]),
                ProjectLink.kind == "github",
            )
        )).scalars().all()
        for link in links:
            github_urls.setdefault(link.project_id, link.url)

    out_items = []
    for p in items:
        data = ProjectListItem.model_validate(p).model_dump()
        data["github_url"] = github_urls.get(p.id)
        out_items.append(ProjectListItem(**data))
    return ProjectListPage(items=out_items, next_cursor=next_cursor)


from app.dependencies.plan_gate import require_under_project_limit


@router.post(
    "",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_under_project_limit)],
)
async def create(
    body: ProjectCreate,
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectOut:
    project = await create_project(
        db,
        workspace_id=auth.active_workspace_id,
        slug=body.slug,
        name=body.name,
        emoji=body.emoji,
        color=body.color,
        pitch=body.pitch,
        status=body.status,
    )
    await db.commit()
    return _to_out(project)


@router.get("/{slug}", response_model=ProjectFullOut)
async def get(
    ctx: Annotated[ProjectContext, Depends(require_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectFullOut:
    ctx_row = await children_svc.get_context(db, ctx.project)
    infra_row = await children_svc.get_infra(db, ctx.project)
    repos = await children_svc.list_repos(db, ctx.project)
    envs = await children_svc.list_environments(db, ctx.project)
    links = await children_svc.list_links(db, ctx.project)
    commands = await children_svc.list_commands(db, ctx.project)
    stack = await children_svc.list_stack(db, ctx.project)
    tags = await children_svc.list_tags(db, ctx.project)

    base = _to_out(ctx.project)
    return ProjectFullOut(
        **base.model_dump(),
        context=ContextOut.model_validate(ctx_row) if ctx_row else None,
        infra=InfraOut.model_validate(infra_row) if infra_row else None,
        repos=[RepoOut.model_validate(r) for r in repos],
        environments=[EnvironmentOut.model_validate(e) for e in envs],
        links=[LinkOut.model_validate(link) for link in links],
        commands=[CommandOut.model_validate(c) for c in commands],
        stack=[
            StackOut(stack_item_slug=si.slug, name=si.name, kind=si.kind, role=ps.role)
            for si, ps in stack
        ],
        tags=[TagOut.model_validate(t) for t in tags],
    )


@router.patch("/{slug}", response_model=ProjectOut)
async def patch(
    body: ProjectUpdate,
    ctx: Annotated[ProjectContext, Depends(require_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectOut:
    await update_project(
        db,
        project=ctx.project,
        name=body.name,
        emoji=body.emoji,
        color=body.color,
        pitch=body.pitch,
        status=body.status,
        is_public=body.is_public,
    )
    await db.commit()
    return _to_out(ctx.project)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    ctx: Annotated[ProjectContext, Depends(require_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await delete_project(db, project=ctx.project)
    await db.commit()


@router.post("/{slug}/switch", response_model=ProjectOut)
async def switch(
    ctx: Annotated[ProjectContext, Depends(require_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectOut:
    await set_active_project(
        db,
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        project=ctx.project,
    )
    await db.commit()
    return _to_out(ctx.project)


@router.post("/{slug}/repo/resync", response_model=ProjectOut)
async def resync_repo(
    ctx: Annotated[ProjectContext, Depends(require_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectOut:
    from sqlalchemy import select

    from app.models import ProjectRepo
    from app.services import github as github_svc
    from app.services import integration as integ_svc

    # Find the first repo with a GitHub-style git_url
    repos = list((await db.execute(
        select(ProjectRepo)
        .where(ProjectRepo.project_id == ctx.project.id)
        .order_by(ProjectRepo.id.asc())
    )).scalars())

    gh_repo = next((r for r in repos if r.git_url and "github.com" in r.git_url), None)
    if gh_repo is None:
        return _to_out(ctx.project)

    # Parse owner/name out of git_url (supports https and ssh forms)
    import re
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?$", gh_repo.git_url or "")
    if not m:
        return _to_out(ctx.project)
    owner, name = m.group(1), m.group(2)

    token = await integ_svc.get_decrypted_token(
        db, workspace_id=ctx.workspace.id, kind="github",
    )
    gh = await github_svc.get_repo(token, owner, name)
    norm = github_svc.normalize_repo(gh)

    gh_repo.default_branch = norm["default_branch"]
    gh_repo.primary_lang = norm.get("language")
    gh_repo.license = norm.get("license_spdx")
    if not ctx.project.pitch and norm.get("description"):
        ctx.project.pitch = norm["description"]

    await db.commit()
    return _to_out(ctx.project)
