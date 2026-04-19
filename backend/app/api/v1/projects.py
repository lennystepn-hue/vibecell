"""Projects CRUD + active-project switch."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, ProjectContext, require_auth, require_project
from app.models import Project
from app.schemas.project import (
    ProjectCreate,
    ProjectListItem,
    ProjectListPage,
    ProjectOut,
    ProjectUpdate,
)
from app.services.project import (
    create_project,
    delete_project,
    list_projects,
    set_active_project,
    update_project,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _to_out(project: Project) -> ProjectOut:
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
    return ProjectListPage(
        items=[ProjectListItem.model_validate(p) for p in items],
        next_cursor=next_cursor,
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
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


@router.get("/{slug}", response_model=ProjectOut)
async def get(
    ctx: Annotated[ProjectContext, Depends(require_project)],
) -> ProjectOut:
    return _to_out(ctx.project)


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
