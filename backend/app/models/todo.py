"""ProjectTodo — per-project task list with batch grouping.

Status flow: open → in_progress → done (or cancelled). Claude can transition
via the MCP tools (todo_start, todo_complete); the user can click in the UI.
`completed_by` tags whether the closure was user-driven or claude-driven so
we can visualise "how much did the AI do" at a glance.
"""
from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ulid_pk


class ProjectTodo(Base):
    __tablename__ = "project_todos"

    id: Mapped[str] = ulid_pk()
    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    batch: Mapped[str | None] = mapped_column(String(120), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="open"
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completed_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    completion_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
