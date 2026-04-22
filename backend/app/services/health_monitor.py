"""Health monitoring service — probes project healthcheck URLs.

Spec 5A.1 — Auto-Signals. Full persistence implementation.

- probe_all() fires HTTP probes and writes to project_health_events.
- After writing events, upserts project_health_summary with rolling-window
  uptime/latency aggregates (24 h and 7 d).
- Uses session_scope() since this runs in APScheduler context.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import Integer, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.db import session_scope
from app.core.ulid import new_ulid
from app.models.signals import ProjectHealthEvent, ProjectHealthSummary

logger = logging.getLogger(__name__)

_PROBE_SEMAPHORE = asyncio.Semaphore(50)
_PROBE_TIMEOUT_S = 10.0


@dataclass
class ProbeResult:
    project_id: str
    project_slug: str
    url: str
    status: str  # up | down | timeout | error
    http_status_code: int | None
    latency_ms: int | None
    error_msg: str | None
    probed_at: datetime


# ---------------------------------------------------------------------------
# HTTP probe
# ---------------------------------------------------------------------------


async def _probe_one(project_id: str, project_slug: str, url: str) -> ProbeResult:
    probed_at = datetime.now(timezone.utc)
    async with _PROBE_SEMAPHORE:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                max_redirects=3,
                timeout=_PROBE_TIMEOUT_S,
            ) as client:
                t0 = asyncio.get_event_loop().time()
                response = await client.get(url)
                latency_ms = int((asyncio.get_event_loop().time() - t0) * 1000)

                st = "up" if response.status_code < 400 else "down"
                return ProbeResult(
                    project_id=project_id,
                    project_slug=project_slug,
                    url=url,
                    status=st,
                    http_status_code=response.status_code,
                    latency_ms=latency_ms,
                    error_msg=None if st == "up" else f"HTTP {response.status_code}",
                    probed_at=probed_at,
                )

        except httpx.TimeoutException:
            return ProbeResult(
                project_id=project_id,
                project_slug=project_slug,
                url=url,
                status="timeout",
                http_status_code=None,
                latency_ms=None,
                error_msg="timeout after 10s",
                probed_at=probed_at,
            )
        except Exception as exc:  # noqa: BLE001
            return ProbeResult(
                project_id=project_id,
                project_slug=project_slug,
                url=url,
                status="error",
                http_status_code=None,
                latency_ms=None,
                error_msg=str(exc)[:200],
                probed_at=probed_at,
            )


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


async def _persist_results(results: list[ProbeResult]) -> None:
    """Write events + upsert summaries inside a single DB transaction."""
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)

    async with session_scope() as db:
        # 1. Insert events
        for r in results:
            db.add(ProjectHealthEvent(
                id=new_ulid(),
                project_id=r.project_id,
                probed_at=r.probed_at,
                status=r.status,
                http_status_code=r.http_status_code,
                latency_ms=r.latency_ms,
                error_msg=r.error_msg,
            ))
        await db.flush()

        # 2. Compute rolling summaries per project
        project_ids = list({r.project_id for r in results})

        # 24h uptime
        rows_24h = (await db.execute(
            select(
                ProjectHealthEvent.project_id,
                func.count(ProjectHealthEvent.id).label("total"),
                func.sum(
                    func.cast(ProjectHealthEvent.status == "up", Integer)
                ).label("up_count"),
                func.avg(ProjectHealthEvent.latency_ms).label("avg_lat"),
            )
            .where(ProjectHealthEvent.project_id.in_(project_ids))
            .where(ProjectHealthEvent.probed_at >= cutoff_24h)
            .group_by(ProjectHealthEvent.project_id)
        )).all()

        # 7d uptime
        rows_7d = (await db.execute(
            select(
                ProjectHealthEvent.project_id,
                func.count(ProjectHealthEvent.id).label("total"),
                func.sum(
                    func.cast(ProjectHealthEvent.status == "up", Integer)
                ).label("up_count"),
            )
            .where(ProjectHealthEvent.project_id.in_(project_ids))
            .where(ProjectHealthEvent.probed_at >= cutoff_7d)
            .group_by(ProjectHealthEvent.project_id)
        )).all()

        uptime_24 = {
            row.project_id: (
                round(row.up_count / row.total * 100, 1) if row.total else None,
                int(row.avg_lat) if row.avg_lat is not None else None,
            )
            for row in rows_24h
        }
        uptime_7 = {
            row.project_id: round(row.up_count / row.total * 100, 1) if row.total else None
            for row in rows_7d
        }

        # Build latest result per project (last in the batch)
        latest: dict[str, ProbeResult] = {}
        for r in results:
            existing = latest.get(r.project_id)
            if existing is None or r.probed_at > existing.probed_at:
                latest[r.project_id] = r

        # 3. Upsert summaries
        for pid, r in latest.items():
            u24, avg_lat = uptime_24.get(pid, (None, None))
            u7 = uptime_7.get(pid)

            stmt = (
                pg_insert(ProjectHealthSummary)
                .values(
                    project_id=pid,
                    last_status=r.status,
                    last_probed_at=r.probed_at,
                    uptime_24h_pct=u24,
                    uptime_7d_pct=u7,
                    avg_latency_ms=avg_lat,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["project_id"],
                    set_={
                        "last_status": r.status,
                        "last_probed_at": r.probed_at,
                        "uptime_24h_pct": u24,
                        "uptime_7d_pct": u7,
                        "avg_latency_ms": avg_lat,
                        "updated_at": now,
                    },
                )
            )
            await db.execute(stmt)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def probe_all() -> None:
    """Iterate all projects with a healthcheck link and probe them.

    Called every 5 minutes by APScheduler (see health_cron.py).
    """
    from app.models.project import Project, ProjectLink

    async with session_scope() as db:
        rows = (await db.execute(
            select(Project.id, Project.slug, ProjectLink.url)
            .join(ProjectLink, ProjectLink.project_id == Project.id)
            .where(ProjectLink.kind == "healthcheck")
            .where(Project.archived_at.is_(None))
        )).all()

    if not rows:
        logger.debug("health_monitor.probe_all: no projects with healthcheck links")
        return

    logger.info("health_monitor.probe_all: probing %d projects", len(rows))

    tasks = [
        _probe_one(project_id=row[0], project_slug=row[1], url=row[2])
        for row in rows
    ]
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    good: list[ProbeResult] = []
    for r in results_raw:
        if isinstance(r, BaseException):
            logger.error("health_monitor: probe task raised: %s", r)
        else:
            good.append(r)  # type: ignore[arg-type]

    if good:
        await _persist_results(good)

    up = sum(1 for r in good if r.status == "up")
    down = len(good) - up
    logger.info("health_monitor: %d projects, %d up, %d down", len(good), up, down)


async def get_project_health_summary(project_id: str) -> dict[str, object] | None:
    """Return the latest health summary for a project, or None if no data yet."""
    async with session_scope() as db:
        row = (await db.execute(
            select(ProjectHealthSummary).where(ProjectHealthSummary.project_id == project_id)
        )).scalar_one_or_none()

    if row is None:
        return None

    return {
        "last_status": row.last_status,
        "last_probed_at": row.last_probed_at.isoformat() if row.last_probed_at else None,
        "uptime_24h_pct": row.uptime_24h_pct,
        "uptime_7d_pct": row.uptime_7d_pct,
        "avg_latency_ms_24h": row.avg_latency_ms,
        "updated_at": row.updated_at.isoformat(),
    }
