"""SQLAlchemy models. Import from here to ensure all tables are registered on Base.metadata."""

from app.models.auth import (
    AuditLog,
    CliDevice,
    EmailChangeToken,
    MagicLinkToken,
    User,
    Workspace,
    WorkspaceMember,
)
from app.models.base import Base
from app.models.billing import Plan, StripeEvent, Subscription
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
from app.models.screenshot import ProjectScreenshot
from app.models.secret import ProjectSecretRef
from app.models.ship_loop import (
    Decision,
    Idea,
    Launch,
    LifecycleEvent,
    Note,
    Session,
    Ship,
)
from app.models.signals import (
    PortfolioSnapshot,
    ProjectHealthEvent,
    ProjectHealthSummary,
)
from app.models.todo import ProjectTodo

__all__ = [
    "ActiveProject",
    "AuditLog",
    "Base",
    "CliDevice",
    "Decision",
    "EmailChangeToken",
    "Idea",
    "Integration",
    "Launch",
    "LifecycleEvent",
    "MagicLinkToken",
    "Note",
    "Plan",
    "PortfolioSnapshot",
    "Project",
    "ProjectCommand",
    "ProjectContext",
    "ProjectEnvironment",
    "ProjectGroup",
    "ProjectHealthEvent",
    "ProjectHealthSummary",
    "ProjectInfra",
    "ProjectLink",
    "ProjectRepo",
    "ProjectScreenshot",
    "ProjectSecretRef",
    "ProjectStack",
    "ProjectTag",
    "ProjectTodo",
    "Session",
    "Ship",
    "StackItem",
    "StripeEvent",
    "Subscription",
    "Tag",
    "User",
    "Workspace",
    "WorkspaceKey",
    "WorkspaceMember",
]
