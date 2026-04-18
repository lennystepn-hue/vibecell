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

__all__ = [
    "AuditLog",
    "Base",
    "CliDevice",
    "MagicLinkToken",
    "User",
    "Workspace",
    "WorkspaceMember",
]
