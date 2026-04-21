"""ORM models for Auto-Signals (Spec 5A) and Portfolio-Intel (Spec 5B)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ulid_pk


class ProjectHealthEvent(Base):
    """One probe result per project per run."""

    __tablename__ = "project_health_events"

    id: Mapped[str] = ulid_pk()
    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    probed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # up|down|timeout|error
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProjectHealthSummary(Base):
    """Rolling summary per project — one row, upserted after every probe batch."""

    __tablename__ = "project_health_summary"

    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    last_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    last_probed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    uptime_24h_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    uptime_7d_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class PortfolioSnapshot(Base):
    """Append-only cached snapshot per workspace."""

    __tablename__ = "portfolio_snapshot"

    id: Mapped[str] = ulid_pk()
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
