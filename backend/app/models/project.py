from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, ulid_pk


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_projects_workspace_slug"),
    )

    id: Mapped[str] = ulid_pk()
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(16))
    color: Mapped[str | None] = mapped_column(String(20))
    pitch: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="building", index=True)
    legal_entity_id: Mapped[str | None] = mapped_column(String(26))  # FK added in Spec 4
    is_public: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class ActiveProject(Base):
    __tablename__ = "active_project"

    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    set_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )


class ProjectRepo(Base):
    __tablename__ = "project_repos"

    id: Mapped[str] = ulid_pk()
    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str | None] = mapped_column(String(20))
    git_url: Mapped[str | None] = mapped_column(Text)
    default_branch: Mapped[str | None] = mapped_column(String(100), default="main")
    local_path: Mapped[str | None] = mapped_column(Text)
    primary_lang: Mapped[str | None] = mapped_column(String(50))
    license: Mapped[str | None] = mapped_column(String(50))


class ProjectEnvironment(Base):
    __tablename__ = "project_environments"

    id: Mapped[str] = ulid_pk()
    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    env_template_path: Mapped[str | None] = mapped_column(Text)
    db_alias: Mapped[str | None] = mapped_column(String(100))


class ProjectInfra(Base):
    __tablename__ = "project_infra"

    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    server_alias: Mapped[str | None] = mapped_column(String(100))
    domain_primary: Mapped[str | None] = mapped_column(String(255))
    domains: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    dns_provider: Mapped[str | None] = mapped_column(String(50))
    db_host: Mapped[str | None] = mapped_column(String(255))
    cdn: Mapped[str | None] = mapped_column(String(50))
    object_storage: Mapped[str | None] = mapped_column(String(255))


class ProjectContext(Base):
    __tablename__ = "project_context"

    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    current_focus: Mapped[str | None] = mapped_column(Text)
    next_step: Mapped[str | None] = mapped_column(Text)
    user_wants: Mapped[str | None] = mapped_column(Text)
    open_questions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    known_issues: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    blocked_by: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )


class ProjectLink(Base):
    __tablename__ = "project_links"
    __table_args__ = (
        # project-scoped index on kind for "all stripe links for a project"
    )

    id: Mapped[str] = ulid_pk()
    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str | None] = mapped_column(String(50), index=True)
    label: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text, nullable=False)


class ProjectCommand(Base):
    __tablename__ = "project_commands"

    id: Mapped[str] = ulid_pk()
    project_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    run_in: Mapped[str] = mapped_column(String(20), nullable=False, default="terminal")
    confirm_required: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
