"""Per-project /launches routes (PH/HN/X/etc.)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import ProjectContext, require_project
from app.schemas.launch import LaunchIn, LaunchOut, LaunchUpdate
from app.services import launch_svc

router = APIRouter(prefix="/api/v1/projects/{slug}/launches", tags=["launches"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CtxDep = Annotated[ProjectContext, Depends(require_project)]


@router.get("", response_model=list[LaunchOut])
async def list_(ctx: CtxDep, db: DbDep) -> list[LaunchOut]:
    rows = await launch_svc.list_launches(db, project=ctx.project)
    return [LaunchOut.model_validate(r) for r in rows]


@router.post("", response_model=LaunchOut, status_code=status.HTTP_201_CREATED)
async def create(body: LaunchIn, ctx: CtxDep, db: DbDep) -> LaunchOut:
    row = await launch_svc.create_launch(
        db,
        project=ctx.project,
        platform=body.platform,
        launched_at=body.launched_at,
        url=body.url,
        metrics=body.metrics,
    )
    await db.commit()
    return LaunchOut.model_validate(row)


@router.patch("/{launch_id}", response_model=LaunchOut)
async def patch(
    launch_id: Annotated[str, Path(min_length=26, max_length=26)],
    body: LaunchUpdate,
    ctx: CtxDep,
    db: DbDep,
) -> LaunchOut:
    row = await launch_svc.update_launch(
        db,
        project=ctx.project,
        launch_id=launch_id,
        url=body.url,
        metrics=body.metrics,
    )
    await db.commit()
    return LaunchOut.model_validate(row)
