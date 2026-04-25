"""MCP tool-call audit logging. Write-only at call-site; Connections UI reads aggregated."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ulid import new_ulid
from app.models.base import Base


class McpAuditLog(Base):
    __tablename__ = "mcp_audit_log"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Slug of the project the tool acted on, or NULL for workspace-scoped
    # tools (vibecell_list / search / recent_projects / ping / switch).
    # Drives per-project filtering of the activity feed.
    project_slug: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)   # "ok" | "error" | "denied"


async def log_tool_call(
    db: AsyncSession, *, client_id: str, workspace_id: str, user_id: str,
    tool_name: str, duration_ms: int, status: str,
    project_slug: str | None = None,
) -> None:
    db.add(McpAuditLog(
        id=new_ulid(),
        client_id=client_id,
        workspace_id=workspace_id,
        user_id=user_id,
        project_slug=project_slug,
        tool_name=tool_name,
        called_at=datetime.now(UTC),
        duration_ms=duration_ms,
        status=status,
    ))
