"""Health monitoring cron job — Spec 5A Auto-Signals.

Registers probe_all() on a 5-minute interval in the shared APScheduler
instance defined in main.py.

Usage in main.py:
    from app.jobs.health_cron import schedule_health_jobs

    def lifespan(app):
        schedule_health_jobs(_scheduler)
        ...
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.health_monitor import probe_all

logger = logging.getLogger(__name__)


def schedule_health_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register health probe jobs on the given scheduler.

    Called once from main.py lifespan context. Jobs are idempotent —
    adding the same job_id twice raises ConflictingIdError, so guard with
    replace_existing=True.
    """
    scheduler.add_job(
        probe_all,
        "interval",
        minutes=5,
        id="health_probe_all",
        replace_existing=True,
        max_instances=1,  # don't pile up if a run is slow
        coalesce=True,
    )
    logger.info("health_cron: registered health_probe_all every 5 minutes")
