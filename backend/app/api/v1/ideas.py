"""Workspace-scoped /ideas + per-project alias."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, ProjectContext, require_auth, require_project
from app.schemas.idea import IdeaIn, IdeaOut, IdeaUpdate
from app.services import idea_svc

router = APIRouter(tags=["ideas"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("/api/v1/ideas", response_model=list[IdeaOut])
async def list_(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: DbDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    project: Annotated[str | None, Query(alias="project")] = None,
) -> list[IdeaOut]:
    rows = await idea_svc.list_ideas(
        db,
        workspace_id=auth.active_workspace_id,
        status=status_filter,
        project_id=project,
    )
    return [IdeaOut.model_validate(r) for r in rows]


@router.post(
    "/api/v1/ideas",
    response_model=IdeaOut,
    status_code=status.HTTP_201_CREATED,
)
async def create(
    body: IdeaIn,
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: DbDep,
) -> IdeaOut:
    row = await idea_svc.create_idea(
        db,
        workspace_id=auth.active_workspace_id,
        body=body.body,
        project_id=body.project_id,
        source=body.source,
    )
    await db.commit()
    return IdeaOut.model_validate(row)


@router.patch("/api/v1/ideas/{idea_id}", response_model=IdeaOut)
async def patch(
    idea_id: Annotated[str, Path(min_length=26, max_length=26)],
    body: IdeaUpdate,
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: DbDep,
) -> IdeaOut:
    row = await idea_svc.update_idea(
        db,
        workspace_id=auth.active_workspace_id,
        idea_id=idea_id,
        status=body.status,
        project_id=body.project_id,
        body=body.body,
    )
    await db.commit()
    return IdeaOut.model_validate(row)


@router.delete(
    "/api/v1/ideas/{idea_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete(
    idea_id: Annotated[str, Path(min_length=26, max_length=26)],
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: DbDep,
) -> None:
    await idea_svc.delete_idea(
        db, workspace_id=auth.active_workspace_id, idea_id=idea_id
    )
    await db.commit()


@router.post(
    "/api/v1/projects/{slug}/ideas",
    response_model=IdeaOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_for_project(
    body: IdeaIn,
    ctx: Annotated[ProjectContext, Depends(require_project)],
    db: DbDep,
) -> IdeaOut:
    row = await idea_svc.create_idea(
        db,
        workspace_id=ctx.workspace.id,
        body=body.body,
        project_id=ctx.project.id,
        source=body.source,
    )
    await db.commit()
    return IdeaOut.model_validate(row)
