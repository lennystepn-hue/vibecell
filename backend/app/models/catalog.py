from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ulid_pk


class StackItem(Base):
    __tablename__ = "stack_items"

    id: Mapped[str] = ulid_pk()
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str | None] = mapped_column(String(30))
    icon_url: Mapped[str | None] = mapped_column(Text)


class ProjectStack(Base):
    __tablename__ = "project_stack"

    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    stack_item_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("stack_items.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str | None] = mapped_column(String(20))


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_tags_workspace_name"),
    )

    id: Mapped[str] = ulid_pk()
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str | None] = mapped_column(String(20))


class ProjectTag(Base):
    __tablename__ = "project_tags"

    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class ProjectGroup(Base):
    __tablename__ = "project_groups"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_project_groups_workspace_slug"),
    )

    id: Mapped[str] = ulid_pk()
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str | None] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
