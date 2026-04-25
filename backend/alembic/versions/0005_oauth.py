"""oauth clients codes access refresh

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-20 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False, unique=True),
        sa.Column("client_name", sa.String(255)),
        sa.Column("redirect_uris", sa.ARRAY(sa.String), nullable=False),
        sa.Column("scope", sa.String(255), nullable=False, server_default="vibecell:tools"),
        sa.Column("registered_by_user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_oauth_clients_client_id", "oauth_clients", ["client_id"])
    op.create_index("ix_oauth_clients_registered_by_user_id", "oauth_clients", ["registered_by_user_id"])

    op.create_table(
        "oauth_auth_codes",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("client_id", sa.String(64), sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("redirect_uri", sa.String(500), nullable=False),
        sa.Column("code_challenge", sa.String(128), nullable=False),
        sa.Column("scope", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_oauth_auth_codes_code", "oauth_auth_codes", ["code"])

    op.create_table(
        "oauth_access_tokens",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("jti", sa.String(26), nullable=False, unique=True),
        sa.Column("client_id", sa.String(64), sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(255), nullable=False),
        sa.Column("issued_from_refresh_family", sa.String(26)),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_oauth_access_tokens_jti", "oauth_access_tokens", ["jti"])
    op.create_index("ix_oauth_access_tokens_client_id", "oauth_access_tokens", ["client_id"])
    op.create_index("ix_oauth_access_tokens_workspace_id", "oauth_access_tokens", ["workspace_id"])
    op.create_index("ix_oauth_access_tokens_family", "oauth_access_tokens", ["issued_from_refresh_family"])

    op.create_table(
        "oauth_refresh_tokens",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("family_id", sa.String(26), nullable=False),
        sa.Column("client_id", sa.String(64), sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(255), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_oauth_refresh_tokens_token_hash", "oauth_refresh_tokens", ["token_hash"])
    op.create_index("ix_oauth_refresh_tokens_family", "oauth_refresh_tokens", ["family_id"])
    op.create_index("ix_refresh_client_user", "oauth_refresh_tokens", ["client_id", "user_id"])


def downgrade() -> None:
    op.drop_table("oauth_refresh_tokens")
    op.drop_table("oauth_access_tokens")
    op.drop_table("oauth_auth_codes")
    op.drop_table("oauth_clients")
