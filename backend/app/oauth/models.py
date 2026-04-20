"""SQLAlchemy ORM models for OAuth 2.1 authorization server.

See docs/superpowers/specs/2026-04-20-spec-3-5-remote-mcp-oauth-design.md.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OAuthClient(Base):
    __tablename__ = "oauth_clients"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_name: Mapped[str | None] = mapped_column(String(255))
    redirect_uris: Mapped[list[str]] = mapped_column(ARRAY(String))
    scope: Mapped[str] = mapped_column(String(255), default="vibecell:tools")
    registered_by_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id"), index=True
    )
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthAuthCode(Base):
    __tablename__ = "oauth_auth_codes"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("oauth_clients.client_id"))
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"))
    workspace_id: Mapped[str] = mapped_column(String(26), ForeignKey("workspaces.id"))
    redirect_uri: Mapped[str] = mapped_column(String(500))
    code_challenge: Mapped[str] = mapped_column(String(128))
    scope: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthAccessToken(Base):
    __tablename__ = "oauth_access_tokens"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    jti: Mapped[str] = mapped_column(String(26), unique=True, index=True)
    client_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("oauth_clients.client_id"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"))
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id"), index=True
    )
    scope: Mapped[str] = mapped_column(String(255))
    issued_from_refresh_family: Mapped[str | None] = mapped_column(String(26), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthRefreshToken(Base):
    __tablename__ = "oauth_refresh_tokens"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    family_id: Mapped[str] = mapped_column(String(26), index=True)
    client_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("oauth_clients.client_id"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"))
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id"), index=True
    )
    scope: Mapped[str] = mapped_column(String(255))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_refresh_client_user", "client_id", "user_id"),
    )
