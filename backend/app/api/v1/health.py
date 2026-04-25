"""Health API — project health summaries.

Spec 5A.1 — Auto-Signals.
GET /api/v1/projects/{slug}/health
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import ProjectContext, require_project
from app.models.signals import ProjectHealthEvent, ProjectHealthSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{slug}", tags=["health"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CtxDep = Annotated[ProjectContext, Depends(require_project)]


@router.get("/health")
async def get_health(ctx: CtxDep, db: DbDep) -> JSONResponse:
    """Return the latest health summary + last-24h events for a project.

    Returns 200 with {status: "not_probed_yet"} if health monitoring has not
    run yet (including when no healthcheck link is configured).
    """
    project = ctx.project

    summary = (await db.execute(
        select(ProjectHealthSummary).where(ProjectHealthSummary.project_id == project.id)
    )).scalar_one_or_none()

    if summary is None:
        # Check if the project has a healthcheck link at all
        from app.models.project import ProjectLink
        link = (await db.execute(
            select(ProjectLink).where(
                ProjectLink.project_id == project.id,
                ProjectLink.kind == "healthcheck",
            )
        )).scalar_one_or_none()

        if link is None:
            return JSONResponse(content={
                "project_id": project.id,
                "slug": project.slug,
                "status": "not_configured",
                "message": "Add a healthcheck link to this project to enable health monitoring.",
            })

        return JSONResponse(content={
            "project_id": project.id,
            "slug": project.slug,
            "status": "not_probed_yet",
            "message": "Health probe has not run yet. First result within 5 minutes.",
            "healthcheck_url": link.url,
        })

    # Fetch the last 24 events for timeline display
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    recent_events = (await db.execute(
        select(ProjectHealthEvent)
        .where(ProjectHealthEvent.project_id == project.id)
        .where(ProjectHealthEvent.probed_at >= cutoff)
        .order_by(ProjectHealthEvent.probed_at.desc())
        .limit(24)
    )).scalars().all()

    return JSONResponse(content={
        "project_id": project.id,
        "slug": project.slug,
        "last_status": summary.last_status,
        "last_probed_at": summary.last_probed_at.isoformat() if summary.last_probed_at else None,
        "uptime_24h_pct": summary.uptime_24h_pct,
        "uptime_7d_pct": summary.uptime_7d_pct,
        "avg_latency_ms_24h": summary.avg_latency_ms,
        "events_last_24h": [
            {
                "probed_at": e.probed_at.isoformat(),
                "status": e.status,
                "http_code": e.http_status_code,
                "latency_ms": e.latency_ms,
            }
            for e in recent_events
        ],
    })
