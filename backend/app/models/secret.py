from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ulid_pk


class ProjectSecretRef(Base):
    __tablename__ = "project_secret_refs"
    __table_args__ = (
        UniqueConstraint("project_id", "label", name="uq_project_secret_refs_project_label"),
    )

    id: Mapped[str] = ulid_pk()
    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    reference: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
