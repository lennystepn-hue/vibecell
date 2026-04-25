from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, ulid_pk


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = ulid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    handle: Mapped[str | None] = mapped_column(String(50), unique=True)
    passkey_credentials: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Set on first successful magic-link verify. Magic-link auth IS email
    # verification (the user demonstrated control of the address by clicking
    # the link). This column makes that fact queryable by downstream code
    # (Stripe customer creation, support tooling, account-change flows).
    # See docs/superpowers/decisions/2026-04-25-email-verification-already-implicit.md
    email_verified_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[str] = ulid_pk()
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="owner")


class CliDevice(Base):
    __tablename__ = "cli_devices"

    id: Mapped[str] = ulid_pk()
    user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(100))
    paired_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = ulid_pk()
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    op: Mapped[str] = mapped_column(String(20), nullable=False)
    entity: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Text (not String(26)) because composite-PK entities serialise as
    # "v1:v2" (e.g. workspace_members → "<workspace_id>:<user_id>" = 53 chars).
    entity_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    diff: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class MagicLinkToken(Base):
    __tablename__ = "magic_link_tokens"

    id: Mapped[str] = ulid_pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class EmailChangeToken(Base):
    """Spec-6 Sprint A2: token mailed to a user's NEW email when they want to
    change their address. Separate from MagicLinkToken because the security
    semantics differ: this token is bound to a specific user_id + new_email
    pair, while a magic-link token only proves "someone controls this address"."""

    __tablename__ = "email_change_tokens"

    id: Mapped[str] = ulid_pk()
    user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    new_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
