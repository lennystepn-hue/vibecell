"""SQLAlchemy models. Import from here to ensure all tables are registered on Base.metadata."""

from app.models.auth import (
    AuditLog,
    CliDevice,
    MagicLinkToken,
    User,
    Workspace,
    WorkspaceMember,
)
from app.models.base import Base
from app.models.catalog import ProjectStack, ProjectTag, StackItem, Tag
from app.models.project import (
    ActiveProject,
    Project,
    ProjectCommand,
    ProjectContext,
    ProjectEnvironment,
    ProjectInfra,
    ProjectLink,
    ProjectRepo,
)

__all__ = [
    "ActiveProject",
    "AuditLog",
    "Base",
    "CliDevice",
    "MagicLinkToken",
    "Project",
    "ProjectCommand",
    "ProjectContext",
    "ProjectEnvironment",
    "ProjectInfra",
    "ProjectLink",
    "ProjectRepo",
    "ProjectStack",
    "ProjectTag",
    "StackItem",
    "Tag",
    "User",
    "Workspace",
    "WorkspaceMember",
]
