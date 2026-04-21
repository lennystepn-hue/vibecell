"""Portfolio API — cross-project intelligence snapshot.

Spec 5B.1 — Portfolio-Intel.
GET /api/v1/portfolio/snapshot — returns cached snapshot (10 min TTL).
?refresh=true bypasses cache and regenerates.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.services.portfolio_intel import get_or_generate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


@router.get("/snapshot")
async def get_snapshot(
    ctx: AuthDep,
    db: DbDep,
    refresh: bool = Query(default=False, description="Force cache bypass and regenerate snapshot"),
) -> JSONResponse:
    """Return the latest portfolio snapshot for the active workspace.

    Reads from portfolio_snapshot cache if the latest row is <10 minutes old.
    Pass ?refresh=true to skip the cache.
    """
    snapshot = await get_or_generate(
        workspace_id=ctx.active_workspace_id,
        db=db,
        force=refresh,
    )
    return JSONResponse(content=snapshot)
