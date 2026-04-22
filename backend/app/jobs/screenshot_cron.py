"""Hourly project-preview refresh — captures a webp of each non-archived
project's live site and stores it under kind="auto".

Scheduled from main.py's lifespan context.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.db import SessionLocal
from app.services import screenshot_svc

logger = logging.getLogger(__name__)


async def _run_refresh_all() -> None:
    """Open a dedicated DB session and capture screenshots for everyone."""
    async with SessionLocal() as db:
        try:
            count = await screenshot_svc.refresh_all_auto(db)
            logger.info("screenshot_cron: captured %s preview(s)", count)
        except Exception:  # noqa: BLE001
            logger.exception("screenshot_cron: refresh_all_auto crashed")


def schedule_screenshot_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register the hourly auto-preview refresh job."""
    scheduler.add_job(
        _run_refresh_all,
        "interval",
        minutes=60,
        id="screenshot_refresh_all",
        replace_existing=True,
        max_instances=1,  # chromium runs are sequential within this job
        coalesce=True,
    )
    logger.info("screenshot_cron: registered screenshot_refresh_all every 60m")
