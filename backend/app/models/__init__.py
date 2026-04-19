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
from app.models.catalog import ProjectGroup, ProjectStack, ProjectTag, StackItem, Tag
from app.models.integration import Integration, WorkspaceKey
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
from app.models.secret import ProjectSecretRef

__all__ = [
    "ActiveProject",
    "AuditLog",
    "Base",
    "CliDevice",
    "Integration",
    "MagicLinkToken",
    "Project",
    "ProjectCommand",
    "ProjectContext",
    "ProjectEnvironment",
    "ProjectGroup",
    "ProjectInfra",
    "ProjectLink",
    "ProjectRepo",
    "ProjectSecretRef",
    "ProjectStack",
    "ProjectTag",
    "StackItem",
    "Tag",
    "User",
    "Workspace",
    "WorkspaceKey",
    "WorkspaceMember",
]
