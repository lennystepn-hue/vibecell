"""Health monitoring service — probes project healthcheck URLs.

Spec 5A — Auto-Signals.

Status: STUB with real probe skeleton.
- probe_all() iterates projects with healthcheck links and fires HTTP probes.
- Results are logged but not yet persisted to project_health_events.
- Full persistence deferred to Spec 5A.1 implementation phase.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from dataclasses import dataclass

import httpx

from app.core.db import session_scope

logger = logging.getLogger(__name__)

# Maximum simultaneous probes — prevents thundering herd on large workspaces
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


async def _probe_one(
    project_id: str,
    project_slug: str,
    url: str,
) -> ProbeResult:
    """Send a single HTTP probe and return a ProbeResult."""
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

                if response.status_code < 400:
                    return ProbeResult(
                        project_id=project_id,
                        project_slug=project_slug,
                        url=url,
                        status="up",
                        http_status_code=response.status_code,
                        latency_ms=latency_ms,
                        error_msg=None,
                        probed_at=probed_at,
                    )
                else:
                    return ProbeResult(
                        project_id=project_id,
                        project_slug=project_slug,
                        url=url,
                        status="down",
                        http_status_code=response.status_code,
                        latency_ms=latency_ms,
                        error_msg=f"HTTP {response.status_code}",
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


async def _persist_result(result: ProbeResult) -> None:
    """Persist a probe result to project_health_events.

    STUB: logs the result but does not write to the DB yet.
    Full impl: INSERT INTO project_health_events using session_scope(),
    then update project_health_summary if enough events accumulated.
    """
    logger.info(
        "health_monitor: project=%s url=%s status=%s latency=%sms [STUB — not persisted]",
        result.project_slug,
        result.url,
        result.status,
        result.latency_ms,
    )
    # TODO: persist when Spec 5A.1 is implemented
    # async with session_scope() as db:
    #     from python_ulid import ULID
    #     event = ProjectHealthEvent(
    #         id=str(ULID()),
    #         project_id=result.project_id,
    #         probed_at=result.probed_at,
    #         status=result.status,
    #         http_status_code=result.http_status_code,
    #         latency_ms=result.latency_ms,
    #         error_msg=result.error_msg,
    #     )
    #     db.add(event)


async def probe_all() -> None:
    """Iterate all projects with a healthcheck link and probe them.

    Called every 5 minutes by APScheduler (see health_cron.py).
    STUB: loads projects + links from DB, runs probes, logs results.
    Persistence deferred to Spec 5A.1.
    """
    from sqlalchemy import select
    from app.models.project import Project, ProjectLink

    async with session_scope() as db:
        # Find all projects that have a healthcheck link
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
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, BaseException):
            logger.error("health_monitor: probe task raised: %s", result)
            continue
        await _persist_result(result)

    logger.info("health_monitor.probe_all: completed %d probes", len(rows))


async def get_project_health_summary(project_id: str) -> dict[str, object] | None:
    """Return the latest health summary for a project.

    STUB: returns None (summary table not written to yet).
    Full impl: SELECT from project_health_summary WHERE project_id = project_id.
    """
    logger.debug(
        "health_monitor.get_project_health_summary project=%s [STUB]", project_id
    )
    # TODO: query project_health_summary when Spec 5A.1 is implemented
    return None
