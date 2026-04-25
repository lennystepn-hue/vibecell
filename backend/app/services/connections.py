"""Unified Connections view — merges oauth_clients with cli_devices.

Used by /settings/connections page in the frontend.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.audit import McpAuditLog
from app.models import CliDevice
from app.oauth.models import OAuthAccessToken, OAuthClient, OAuthRefreshToken
from app.oauth.tokens import JTIBlacklist


class ConnectionsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        # OAuth clients registered by this user and not revoked
        oauth_rows = (await self.db.execute(
            select(OAuthClient).where(
                OAuthClient.registered_by_user_id == user_id,
                OAuthClient.revoked_at.is_(None),
            )
        )).scalars().all()

        # CLI devices owned by this user
        cli_rows = (await self.db.execute(
            select(CliDevice).where(CliDevice.user_id == user_id)
        )).scalars().all()

        results: list[dict[str, Any]] = []
        for c in oauth_rows:
            stats = await self._client_stats(c.client_id)
            results.append({
                "id": c.id,
                "type": "oauth",
                "name": c.client_name or "Unnamed MCP Client",
                "icon": self._icon_for(c.client_name),
                "connected_at": c.created_at.isoformat() if c.created_at else None,
                "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
                "tool_calls_today": stats["today"],
                "tool_calls_total": stats["total"],
                "workspace_id": None,
            })
        for d in cli_rows:
            results.append({
                "id": d.id,
                "type": "cli",
                # CliDevice has `name` (not `label`)
                "name": f"Device: {d.name or d.id}",
                "icon": "cli",
                "connected_at": _iso(d.paired_at),
                # CliDevice has last_seen_at only (no last_sync_at)
                "last_used_at": _iso(d.last_seen_at),
                "tool_calls_today": 0,
                "tool_calls_total": 0,
                # CliDevice has no workspace_id column
                "workspace_id": None,
            })

        def sort_key(r: dict) -> datetime:
            if r["last_used_at"]:
                return datetime.fromisoformat(r["last_used_at"])
            return datetime.min.replace(tzinfo=UTC)

        results.sort(key=sort_key, reverse=True)
        return results

    async def _client_stats(self, client_id: str) -> dict[str, int]:
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today = (await self.db.execute(
            select(func.count(McpAuditLog.id)).where(
                McpAuditLog.client_id == client_id,
                McpAuditLog.called_at >= today_start,
            )
        )).scalar_one()
        total = (await self.db.execute(
            select(func.count(McpAuditLog.id)).where(McpAuditLog.client_id == client_id)
        )).scalar_one()
        return {"today": int(today), "total": int(total)}

    @staticmethod
    def _icon_for(name: str | None) -> str:
        if not name:
            return "generic"
        lower = name.lower()
        if "claude" in lower:
            return "claude"
        if "cursor" in lower:
            return "cursor"
        if "zed" in lower:
            return "zed"
        if "windsurf" in lower:
            return "windsurf"
        return "generic"

    async def revoke(self, kind: str, connection_id: str) -> None:
        now = datetime.now(UTC)
        if kind == "oauth":
            row = await self.db.get(OAuthClient, connection_id)
            if row is None:
                return
            row.revoked_at = now
            # Blacklist + DB-revoke all live access tokens for this client
            access_rows = (await self.db.execute(
                select(OAuthAccessToken).where(
                    OAuthAccessToken.client_id == row.client_id,
                    OAuthAccessToken.revoked_at.is_(None),
                    OAuthAccessToken.expires_at > now,
                )
            )).scalars().all()
            for ar in access_rows:
                ar.revoked_at = now
                ttl = max(1, int(ar.expires_at.timestamp()) - int(now.timestamp()))
                await JTIBlacklist().add(ar.jti, ttl_seconds=ttl)
            # Invalidate all non-revoked refresh tokens
            refresh_rows = (await self.db.execute(
                select(OAuthRefreshToken).where(
                    OAuthRefreshToken.client_id == row.client_id,
                    OAuthRefreshToken.revoked_at.is_(None),
                )
            )).scalars().all()
            for rr in refresh_rows:
                rr.revoked_at = now
            return

        if kind == "cli":
            row = await self.db.get(CliDevice, connection_id)
            if row is not None:
                await self.db.delete(row)
            return

        raise ValueError(f"Unknown connection kind: {kind}")


def _iso(v: datetime | None) -> str | None:
    return v.isoformat() if v else None
