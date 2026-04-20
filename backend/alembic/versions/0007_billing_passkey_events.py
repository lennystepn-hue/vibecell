"""billing subscriptions + billing events

Revision ID: 0007_billing_passkey_events
Revises: 0006
Create Date: 2026-04-20 00:00:02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # billing_subscriptions — one row per workspace
    op.create_table(
        "billing_subscriptions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(26),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(64), nullable=True),
        sa.Column("plan_id", sa.String(20), nullable=False, server_default="free"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_billing_subscriptions_workspace",
        "billing_subscriptions",
        ["workspace_id"],
    )
    op.create_index(
        "ix_billing_subscriptions_stripe_customer",
        "billing_subscriptions",
        ["stripe_customer_id"],
    )

    # billing_events — append-only Stripe webhook log
    op.create_table(
        "billing_events",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(26),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("stripe_event_id", sa.String(64), nullable=False, unique=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_billing_events_workspace_type",
        "billing_events",
        ["workspace_id", "event_type"],
    )
    op.create_index(
        "ix_billing_events_stripe_event_id",
        "billing_events",
        ["stripe_event_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("billing_events")
    op.drop_table("billing_subscriptions")
