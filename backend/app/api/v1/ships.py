"""Per-project /ships routes (release events)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import ProjectContext, require_project
from app.schemas.ship import ShipIn, ShipOut
from app.services import ship_svc

router = APIRouter(prefix="/api/v1/projects/{slug}/ships", tags=["ships"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CtxDep = Annotated[ProjectContext, Depends(require_project)]


@router.get("", response_model=list[ShipOut])
async def list_(ctx: CtxDep, db: DbDep) -> list[ShipOut]:
    rows = await ship_svc.list_ships(db, project=ctx.project)
    return [ShipOut.model_validate(r) for r in rows]


@router.post("", response_model=ShipOut, status_code=status.HTTP_201_CREATED)
async def create(body: ShipIn, ctx: CtxDep, db: DbDep) -> ShipOut:
    row = await ship_svc.create_ship(
        db,
        project=ctx.project,
        shipped_at=body.shipped_at,
        version=body.version,
        summary=body.summary,
        changelog_md=body.changelog_md,
    )
    await db.commit()
    return ShipOut.model_validate(row)
