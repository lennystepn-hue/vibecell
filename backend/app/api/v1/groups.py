"""Project groups + bulk reorder."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.schemas.group import (
    GroupCreate,
    GroupOut,
    GroupUpdate,
    ReorderRequest,
    ReorderResult,
)
from app.services import group as svc

router = APIRouter(prefix="/api/v1", tags=["groups"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


@router.get("/groups", response_model=list[GroupOut])
async def list_groups(auth: AuthDep, db: DbDep) -> list[GroupOut]:
    rows = await svc.list_groups(db, workspace_id=auth.active_workspace_id)
    return [GroupOut.model_validate(g) for g in rows]


@router.post("/groups", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(body: GroupCreate, auth: AuthDep, db: DbDep) -> GroupOut:
    g = await svc.create_group(
        db,
        workspace_id=auth.active_workspace_id,
        name=body.name,
        slug=body.slug,
        color=body.color,
    )
    await db.commit()
    return GroupOut.model_validate(g)


@router.patch("/groups/{group_id}", response_model=GroupOut)
async def patch_group(
    group_id: Annotated[str, Path(min_length=1)],
    body: GroupUpdate,
    auth: AuthDep,
    db: DbDep,
) -> GroupOut:
    g = await svc.get_group(db, workspace_id=auth.active_workspace_id, group_id=group_id)
    await svc.update_group(db, group=g, name=body.name, color=body.color, position=body.position)
    await db.commit()
    return GroupOut.model_validate(g)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: str, auth: AuthDep, db: DbDep) -> None:
    g = await svc.get_group(db, workspace_id=auth.active_workspace_id, group_id=group_id)
    await svc.delete_group(db, group=g)
    await db.commit()


@router.post("/projects/reorder", response_model=ReorderResult)
async def reorder_projects(body: ReorderRequest, auth: AuthDep, db: DbDep) -> ReorderResult:
    count = await svc.reorder_projects(
        db,
        workspace_id=auth.active_workspace_id,
        items=[(i.slug, i.group_id, i.position) for i in body.items],
    )
    await db.commit()
    return ReorderResult(updated=count)
