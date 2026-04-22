"""ProjectScreenshot — visual history per project.

Four kinds:
- auto: hourly scheduled captures of the project's live site
- ship: captured on every ship event, linked via ship_id
- manual: user-triggered "grab current state"
- moodboard: uploaded inspiration / design reference
"""
from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ulid_pk


class ProjectScreenshot(Base):
    __tablename__ = "project_screenshots"

    id: Mapped[str] = ulid_pk()
    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(
        String(60), nullable=False, server_default="image/webp"
    )
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    ship_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("ships.id", ondelete="SET NULL"), nullable=True
    )
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
