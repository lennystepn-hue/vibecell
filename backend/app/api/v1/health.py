"""Health API — project health summaries.

Spec 5A — Auto-Signals.
GET /api/v1/projects/{slug}/health — returns latest health summary for a project.
Returns 200 with {status: "unknown"} until the health monitor runs.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import ProjectContext, require_project
from app.services.health_monitor import get_project_health_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{slug}", tags=["health"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CtxDep = Annotated[ProjectContext, Depends(require_project)]


@router.get("/health")
async def get_health(ctx: CtxDep, db: DbDep) -> JSONResponse:
    """Return the latest health summary for a project.

    Returns:
    - 200 with health data if a summary exists.
    - 200 with {status: "unknown", message: "..."} if no probes yet.

    The probe runs every 5 min via APScheduler. First result appears
    within 5 minutes of the healthcheck link being configured.
    """
    summary = await get_project_health_summary(project_id=ctx.project.id)

    if summary is None:
        # Check if the project has a healthcheck link at all
        from app.models.project import ProjectLink
        link = (await db.execute(
            select(ProjectLink).where(
                ProjectLink.project_id == ctx.project.id,
                ProjectLink.kind == "healthcheck",
            )
        )).scalar_one_or_none()

        if link is None:
            return JSONResponse(
                content={
                    "project_id": ctx.project.id,
                    "status": "not_configured",
                    "message": "Add a healthcheck link to this project to enable health monitoring.",
                }
            )

        return JSONResponse(
            content={
                "project_id": ctx.project.id,
                "status": "unknown",
                "message": "Health probe has not run yet. First result within 5 minutes.",
                "healthcheck_url": link.url,
            }
        )

    return JSONResponse(content={"project_id": ctx.project.id, **summary})
