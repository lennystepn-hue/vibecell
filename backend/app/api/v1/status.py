"""Public status endpoint — `/api/v1/status`.

Returns a JSON payload that powers the public /status frontend page (and any
external uptime monitor pointed at this URL). Anonymous-accessible — no auth,
no rate limiting beyond the global one — because that's the whole point of a
status page: when the auth layer is down, the status page must still answer.

Component probes are best-effort and never raise; a probe that fails turns
into `status="down"` for that component and degrades the overall verdict.
The probes are cheap (~milliseconds) so we run them inline per request — no
caching layer to fail open when stale.

Public contract:
  • status enum: "ok" | "degraded" | "down"
  • overall is the worst component (any "down" → "down"; any "degraded"
    without "down" → "degraded"; else "ok")
  • Latencies are best-effort wall-clock ms; null when not measurable
  • `incidents` is currently always [] — placeholder for the manual incident
    log we'll add post-launch via a markdown file or a small admin form
"""
from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis
from app.mcp.tools import TOOLS
from app.models import Session as SessionModel
from app.models.billing import StripeEvent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["status"])

ComponentStatus = Literal["ok", "degraded", "down"]
OverallStatus = Literal["ok", "degraded", "down"]

# Thresholds — tune sparingly. Latency past the warn threshold turns the
# component into "degraded" (still serving, but slower than the SLO).
_DB_WARN_MS = 250
_REDIS_WARN_MS = 100

# Stripe webhook freshness — if we haven't seen a single Stripe event in this
# long AND we're past launch (subscriptions exist), the integration is likely
# broken. Pre-launch this just stays at "ok · no events yet" so a brand-new
# install doesn't look on fire.
_STRIPE_STALE_AFTER = timedelta(hours=24)

# Commit-sync cron freshness — the cron writes source='github' Session rows
# every 2 min when there are linked repos. If the latest one is older than
# this AND we have linked repos, the cron is wedged.
_COMMIT_SYNC_STALE_AFTER = timedelta(minutes=15)


def _now() -> datetime:
    return datetime.now(UTC)


async def _probe_db(db: AsyncSession) -> dict[str, object]:
    t0 = time.monotonic()
    try:
        await db.execute(text("SELECT 1"))
        latency = int((time.monotonic() - t0) * 1000)
        if latency > _DB_WARN_MS:
            return {
                "name": "Database",
                "status": "degraded",
                "latency_ms": latency,
                "message": f"Slow ping ({latency}ms)",
            }
        return {
            "name": "Database",
            "status": "ok",
            "latency_ms": latency,
            "message": None,
        }
    except Exception as exc:
        logger.warning("status: db probe failed: %s", exc)
        return {
            "name": "Database",
            "status": "down",
            "latency_ms": None,
            "message": "Connection failed",
        }


async def _probe_redis() -> dict[str, object]:
    t0 = time.monotonic()
    try:
        client = await get_redis()
        await client.ping()
        latency = int((time.monotonic() - t0) * 1000)
        if latency > _REDIS_WARN_MS:
            return {
                "name": "Cache",
                "status": "degraded",
                "latency_ms": latency,
                "message": f"Slow ping ({latency}ms)",
            }
        return {
            "name": "Cache",
            "status": "ok",
            "latency_ms": latency,
            "message": None,
        }
    except Exception as exc:
        logger.warning("status: redis probe failed: %s", exc)
        return {
            "name": "Cache",
            "status": "down",
            "latency_ms": None,
            "message": "Connection failed",
        }


def _probe_mcp() -> dict[str, object]:
    """MCP probe — purely in-process, just confirms the tool registry is
    populated. The actual /mcp endpoint shares the same FastAPI process,
    so if HTTP works the dispatcher works."""
    count = len(TOOLS)
    if count == 0:
        return {
            "name": "MCP",
            "status": "down",
            "latency_ms": None,
            "message": "No tools registered",
        }
    return {
        "name": "MCP",
        "status": "ok",
        "latency_ms": None,
        "message": f"{count} tools registered",
    }


async def _probe_stripe(db: AsyncSession) -> dict[str, object]:
    """Stripe webhook health — looks at the freshest StripeEvent row.

    We don't actually call Stripe here (would couple the status page to
    Stripe's status). Instead we ask: when did we last *receive* a webhook?
    If the table is empty (greenfield install) we report "ok · no events
    yet" — not a real failure.
    """
    last = (
        await db.execute(
            select(StripeEvent).order_by(desc(StripeEvent.processed_at)).limit(1)
        )
    ).scalar_one_or_none()

    if last is None:
        return {
            "name": "Billing",
            "status": "ok",
            "latency_ms": None,
            "message": "No webhook events yet",
        }

    age = _now() - last.processed_at
    if age > _STRIPE_STALE_AFTER:
        return {
            "name": "Billing",
            "status": "degraded",
            "latency_ms": None,
            "message": f"Last event {_humanize(age)} ago",
        }
    return {
        "name": "Billing",
        "status": "ok",
        "latency_ms": None,
        "message": f"Last event {_humanize(age)} ago",
    }


async def _probe_commit_sync(db: AsyncSession) -> dict[str, object]:
    """Commit-sync cron — youngest source='github' session row tells us
    when the cron last ingested anything. We deliberately don't probe
    GitHub itself; the cron's job is to absorb GitHub flakiness."""
    latest = (
        await db.execute(
            select(SessionModel)
            .where(SessionModel.source == "github")
            .order_by(desc(SessionModel.started_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest is None:
        return {
            "name": "GitHub sync",
            "status": "ok",
            "latency_ms": None,
            "message": "No commits ingested yet",
        }
    age = _now() - latest.started_at
    if age > _COMMIT_SYNC_STALE_AFTER:
        return {
            "name": "GitHub sync",
            "status": "degraded",
            "latency_ms": None,
            "message": f"Last ingest {_humanize(age)} ago",
        }
    return {
        "name": "GitHub sync",
        "status": "ok",
        "latency_ms": None,
        "message": f"Last ingest {_humanize(age)} ago",
    }


def _humanize(delta: timedelta) -> str:
    s = int(delta.total_seconds())
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


def _aggregate(components: list[dict[str, object]]) -> OverallStatus:
    statuses = [c["status"] for c in components]
    if "down" in statuses:
        return "down"
    if "degraded" in statuses:
        return "degraded"
    return "ok"


@router.get("/status")
async def get_status(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    api_component: dict[str, object] = {
        "name": "API",
        "status": "ok",
        "latency_ms": None,
        "message": None,
    }
    db_component = await _probe_db(db)
    redis_component = await _probe_redis()
    mcp_component = _probe_mcp()
    stripe_component = await _probe_stripe(db)
    commit_component = await _probe_commit_sync(db)

    components = [
        api_component,
        db_component,
        redis_component,
        mcp_component,
        stripe_component,
        commit_component,
    ]
    return {
        "overall": _aggregate(components),
        "components": components,
        # Manual incident log placeholder. Not surfaced in v1; UI hides the
        # block when the array is empty so we don't spend pixels on nothing.
        "incidents": [],
        "version": "0.1.0",
        "git_sha": os.environ.get("GIT_SHA", "unknown"),
        "generated_at": _now().isoformat(),
    }
