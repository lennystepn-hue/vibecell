"""Portfolio API — cross-project intelligence snapshot.

Spec 5B — Portfolio-Intel.
GET /api/v1/portfolio/snapshot — returns the latest portfolio snapshot for the
active workspace. Generates on-demand if missing or >1h stale.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.services.portfolio_intel import generate_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


@router.get("/snapshot")
async def get_snapshot(ctx: AuthDep, db: DbDep) -> JSONResponse:
    """Return the latest portfolio snapshot for the active workspace.

    Generates a fresh snapshot on-demand (no cache yet).
    Full implementation will cache in portfolio_snapshot table and only
    regenerate when >1h stale.

    The snapshot includes:
    - project_count, active_project_count
    - stagnant_projects (no activity >30d)
    - activity_by_week (rolling 12w, colored heatmap data)
    - recommendations (Phase 5B.3, currently empty)
    - dependency_alerts (Phase 5B.2, currently empty)
    """
    try:
        snapshot = await generate_snapshot(workspace_id=ctx.active_workspace_id)
        return JSONResponse(content=snapshot)
    except Exception as exc:
        logger.exception("portfolio.get_snapshot failed: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            content={
                "error": "snapshot_generation_failed",
                "detail": str(exc),
                "hint": "Full portfolio intelligence deferred to Spec 5B.1",
            },
        )
