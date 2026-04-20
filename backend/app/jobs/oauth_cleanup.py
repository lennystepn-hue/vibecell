"""Daily maintenance — orphan DCR clients + audit log retention."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import session_scope
from app.mcp.audit import McpAuditLog
from app.metrics.registry import mcp_active_connections
from app.oauth.models import OAuthAccessToken, OAuthClient

logger = logging.getLogger(__name__)


async def prune_orphan_clients(db: AsyncSession) -> int:
    s = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=s.oauth_dcr_orphan_ttl_hours)
    result = await db.execute(
        delete(OAuthClient).where(
            OAuthClient.registered_by_user_id.is_(None),
            OAuthClient.created_at < cutoff,
        )
    )
    return result.rowcount or 0


async def prune_audit_log(db: AsyncSession) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    result = await db.execute(
        delete(McpAuditLog).where(McpAuditLog.called_at < cutoff)
    )
    return result.rowcount or 0


async def run_once() -> None:
    async with session_scope() as db:
        orphans = await prune_orphan_clients(db)
        logs = await prune_audit_log(db)
        logger.info("oauth_cleanup: pruned %d orphan clients + %d audit rows", orphans, logs)


async def refresh_active_connections_gauge() -> None:
    async with session_scope() as db:
        now = datetime.now(timezone.utc)
        count = (await db.execute(
            select(func.count(OAuthAccessToken.id)).where(
                OAuthAccessToken.revoked_at.is_(None),
                OAuthAccessToken.expires_at > now,
            )
        )).scalar_one()
        mcp_active_connections.set(count)


if __name__ == "__main__":
    asyncio.run(run_once())
