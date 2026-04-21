from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import ProjectContext, require_project
from app.services.activity import fetch_activity

router = APIRouter(prefix="/api/v1/projects/{slug}/activity", tags=["activity"])


@router.get("")
async def get_activity(
    ctx: Annotated[ProjectContext, Depends(require_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict]:
    return await fetch_activity(db, project=ctx.project, limit=limit)
