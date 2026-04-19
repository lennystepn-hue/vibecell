"""Per-project /lifecycle-events routes."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import ProjectContext, require_project
from app.schemas.lifecycle import LifecycleEventIn, LifecycleEventOut
from app.services import lifecycle_svc

router = APIRouter(
    prefix="/api/v1/projects/{slug}/lifecycle-events", tags=["lifecycle"]
)

DbDep = Annotated[AsyncSession, Depends(get_db)]
CtxDep = Annotated[ProjectContext, Depends(require_project)]


@router.get("", response_model=list[LifecycleEventOut])
async def list_(ctx: CtxDep, db: DbDep) -> list[LifecycleEventOut]:
    rows = await lifecycle_svc.list_events(db, project=ctx.project)
    return [LifecycleEventOut.model_validate(r) for r in rows]


@router.post(
    "", response_model=LifecycleEventOut, status_code=status.HTTP_201_CREATED
)
async def create(
    body: LifecycleEventIn, ctx: CtxDep, db: DbDep
) -> LifecycleEventOut:
    row = await lifecycle_svc.create_event(
        db,
        project=ctx.project,
        at=body.at,
        kind=body.kind,
        detail=body.detail,
    )
    await db.commit()
    return LifecycleEventOut.model_validate(row)
