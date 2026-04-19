"""ORM models for the Ship Loop (Spec 2) — sessions, decisions, ideas,
ships, launches, lifecycle events, notes.

All entities FK to `projects.id` (CASCADE for most; SET NULL for ideas so
project-less ideas linger in the workspace inbox after project deletion).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ulid_pk


class Session(Base):
    """Auto-logged coding block.

    `files_touched` and `commits` are arrays of opaque dicts the skill
    daemon builds (filenames + sha/short metadata).  `source` discriminates
    between automated skill writes, manual UI entries, and CLI captures.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = ulid_pk()
    project_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    summary: Mapped[str | None] = mapped_column(Text)
    files_touched: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    commits: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    next_step: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(30), nullable=False)


class Decision(Base):
    """ADR-lite: title + context + decision + consequences + reconsider_if."""

    __tablename__ = "decisions"

    id: Mapped[str] = ulid_pk()
    project_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    context: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    consequences: Mapped[str | None] = mapped_column(Text)
    reconsider_if: Mapped[str | None] = mapped_column(Text)


class Idea(Base):
    """Per-workspace idea inbox. `project_id` optional — global capture
    lands workspace-level, and the user triages into a project later."""

    __tablename__ = "ideas"

    id: Mapped[str] = ulid_pk()
    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("projects.id", ondelete="SET NULL"),
        index=True,
    )
    captured_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="inbox", server_default="inbox", index=True
    )


class Ship(Base):
    """Release event. Creating a ship also writes a `lifecycle_events` row
    with `kind='ship'` in the same transaction (see ship_svc.create_ship)."""

    __tablename__ = "ships"

    id: Mapped[str] = ulid_pk()
    project_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shipped_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[str | None] = mapped_column(String(50))
    summary: Mapped[str | None] = mapped_column(Text)
    changelog_md: Mapped[str | None] = mapped_column(Text)


class Launch(Base):
    """PH / HN / X / Reddit / newsletter launch event with free-form metrics."""

    __tablename__ = "launches"

    id: Mapped[str] = ulid_pk()
    project_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    launched_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )


class LifecycleEvent(Base):
    """Milestone marker: first_commit / first_user / first_payment / mrr_*
    / ph_launch / viral / ship. `detail` is free-form JSON."""

    __tablename__ = "lifecycle_events"

    id: Mapped[str] = ulid_pk()
    project_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Note(Base):
    """Singleton free-form markdown scratchpad per project."""

    __tablename__ = "notes"

    project_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    markdown: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
