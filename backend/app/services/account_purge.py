"""Spec-6 Sprint A3: GDPR account-delete + data-export.

Two operations:

* ``gather_user_data`` — walk every table that holds rows owned by the user
  (directly via user_id, or transitively via workspace_id where the user is
  the sole/owner member) and serialise to a single dict that the export
  endpoint streams as JSON. Implements GDPR Art. 20 (data portability).

* ``purge`` — delete all data owned by the user. Implements GDPR Art. 17
  (right to erasure). Handles the ``Workspace.owner_id`` ``RESTRICT`` FK
  by deleting solely-owned workspaces first (which cascades through every
  ``project_*`` table), then the user. Workspaces with co-members are NOT
  deleted — the caller gets a 409 Conflict with an actionable message.

Design choices:
* Both operations use plain SQLAlchemy core queries, not ORM, to avoid
  surprises with relationship-loading + cascades-via-Python (we want
  explicit control, traceable behaviour).
* The purge runs in a single transaction. Either everything goes or
  nothing does — partial purges leave the user account in a bizarre
  half-deleted state that's worse than refusing.
* Audit log is intentionally NOT purged for the workspace-the-user-owned;
  rows referencing the (now deleted) workspace become orphan. We don't
  log the deletion itself either — it's the user's data, they want it
  gone, leaving a "user X deleted account at Y" row defeats the purpose.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.models import (
    ActiveProject,
    AuditLog,
    CliDevice,
    Decision,
    EmailChangeToken,
    Idea,
    Launch,
    LifecycleEvent,
    MagicLinkToken,
    Note,
    Project,
    ProjectCommand,
    ProjectContext,
    ProjectEnvironment,
    ProjectInfra,
    ProjectLink,
    ProjectRepo,
    ProjectScreenshot,
    ProjectSecretRef,
    ProjectStack,
    ProjectTag,
    ProjectTodo,
    Session,
    Ship,
    User,
    Workspace,
    WorkspaceKey,
    WorkspaceMember,
)


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy model instance to a JSON-safe dict.
    Datetime → ISO string. Bytes → base64 (rare in our schema). Everything
    else passes through model-attribute access."""
    out: dict[str, Any] = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        if isinstance(val, datetime):
            out[col.name] = val.isoformat()
        elif isinstance(val, bytes):
            import base64
            out[col.name] = "base64:" + base64.b64encode(val).decode()
        else:
            out[col.name] = val
    return out


async def _user_workspace_ids(session: AsyncSession, user_id: str) -> list[str]:
    """All workspace_ids the user is a member of (including owned)."""
    rows = await session.execute(
        select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id)
    )
    return [r[0] for r in rows.all()]


async def _user_owned_workspace_ids(session: AsyncSession, user_id: str) -> list[str]:
    rows = await session.execute(
        select(Workspace.id).where(Workspace.owner_id == user_id)
    )
    return [r[0] for r in rows.all()]


async def gather_user_data(session: AsyncSession, user_id: str) -> dict[str, Any]:
    """Collect every row owned by the user across every table. Returns a dict
    shaped roughly like:
        {
          "exported_at": "2026-04-25T10:00:00Z",
          "user": {...},
          "workspaces": [...],
          "workspace_members": [...],
          "projects": [...],
          ...one key per table...
        }
    Only rows the user has standing to see are included."""
    user_row = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one()

    workspace_ids = await _user_workspace_ids(session, user_id)

    out: dict[str, Any] = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "user": _row_to_dict(user_row),
        "workspaces": [],
        "workspace_members": [],
        "workspace_keys": [],
        "projects": [],
        "project_contexts": [],
        "project_environments": [],
        "project_repos": [],
        "project_infras": [],
        "project_links": [],
        "project_commands": [],
        "project_secrets": [],
        "project_stack": [],
        "project_tags": [],
        "project_screenshots": [],
        "project_todos": [],
        "active_projects": [],
        "sessions": [],
        "decisions": [],
        "ideas": [],
        "ships": [],
        "launches": [],
        "lifecycle_events": [],
        "notes": [],
        "audit_log": [],
        "cli_devices": [],
        "email_change_tokens": [],
        "magic_link_tokens": [],
    }

    if not workspace_ids:
        return out

    # ---- Workspace-scoped tables ----------------------------------------
    out["workspaces"] = [
        _row_to_dict(r)
        for r in (await session.execute(
            select(Workspace).where(Workspace.id.in_(workspace_ids))
        )).scalars().all()
    ]
    out["workspace_members"] = [
        _row_to_dict(r)
        for r in (await session.execute(
            select(WorkspaceMember).where(WorkspaceMember.workspace_id.in_(workspace_ids))
        )).scalars().all()
    ]
    out["workspace_keys"] = [
        _row_to_dict(r)
        for r in (await session.execute(
            select(WorkspaceKey).where(WorkspaceKey.workspace_id.in_(workspace_ids))
        )).scalars().all()
    ]

    project_ids: list[str] = [
        r[0]
        for r in (await session.execute(
            select(Project.id).where(Project.workspace_id.in_(workspace_ids))
        )).all()
    ]

    # ---- Project-scoped tables ------------------------------------------
    if project_ids:
        out["projects"] = [
            _row_to_dict(r)
            for r in (await session.execute(
                select(Project).where(Project.id.in_(project_ids))
            )).scalars().all()
        ]
        for key, model, fk_col in [
            ("project_contexts",     ProjectContext,     ProjectContext.project_id),
            ("project_environments", ProjectEnvironment, ProjectEnvironment.project_id),
            ("project_repos",        ProjectRepo,        ProjectRepo.project_id),
            ("project_infras",       ProjectInfra,       ProjectInfra.project_id),
            ("project_links",        ProjectLink,        ProjectLink.project_id),
            ("project_commands",     ProjectCommand,     ProjectCommand.project_id),
            ("project_secrets",      ProjectSecretRef,   ProjectSecretRef.project_id),
            ("project_stack",        ProjectStack,       ProjectStack.project_id),
            ("project_tags",         ProjectTag,         ProjectTag.project_id),
            ("project_screenshots",  ProjectScreenshot,  ProjectScreenshot.project_id),
            ("project_todos",        ProjectTodo,        ProjectTodo.project_id),
            ("sessions",             Session,            Session.project_id),
            ("decisions",            Decision,           Decision.project_id),
            ("ships",                Ship,               Ship.project_id),
            ("launches",             Launch,             Launch.project_id),
            ("lifecycle_events",     LifecycleEvent,     LifecycleEvent.project_id),
            ("notes",                Note,               Note.project_id),
        ]:
            rows = (await session.execute(
                select(model).where(fk_col.in_(project_ids))
            )).scalars().all()
            out[key] = [_row_to_dict(r) for r in rows]

    # Workspace-scoped — non-project items
    out["active_projects"] = [
        _row_to_dict(r)
        for r in (await session.execute(
            select(ActiveProject).where(ActiveProject.workspace_id.in_(workspace_ids))
        )).scalars().all()
    ]
    out["ideas"] = [
        _row_to_dict(r)
        for r in (await session.execute(
            select(Idea).where(Idea.workspace_id.in_(workspace_ids))
        )).scalars().all()
    ]
    out["audit_log"] = [
        _row_to_dict(r)
        for r in (await session.execute(
            select(AuditLog).where(AuditLog.workspace_id.in_(workspace_ids))
        )).scalars().all()
    ]

    # ---- User-scoped tables (FK to users.id) ----------------------------
    out["cli_devices"] = [
        _row_to_dict(r)
        for r in (await session.execute(
            select(CliDevice).where(CliDevice.user_id == user_id)
        )).scalars().all()
    ]
    out["email_change_tokens"] = [
        _row_to_dict(r)
        for r in (await session.execute(
            select(EmailChangeToken).where(EmailChangeToken.user_id == user_id)
        )).scalars().all()
    ]
    # Magic-link tokens are keyed by email, not user_id — match by current address
    out["magic_link_tokens"] = [
        _row_to_dict(r)
        for r in (await session.execute(
            select(MagicLinkToken).where(MagicLinkToken.email == user_row.email)
        )).scalars().all()
    ]
    return out


async def purge(session: AsyncSession, user_id: str) -> None:
    """Permanently delete every row owned by the user. Implements GDPR
    Art. 17 (right to erasure).

    Refuses (raises ConflictError) if the user owns any workspace that has
    OTHER members — those workspaces are shared resources, the operator
    must explicitly transfer ownership or remove members before delete.

    Side-effect (best-effort): if the user has a live Stripe subscription,
    we cancel it BEFORE deleting their data, so Stripe stops charging
    them. Failure to reach Stripe is logged but doesn't block the purge —
    the user has a clear right to erasure under Art. 17 even if our
    payment processor is temporarily unreachable.
    """
    import logging
    logger = logging.getLogger(__name__)

    user_row = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user_row is None:
        return  # already gone, no-op

    # Cancel Stripe subscription (best-effort) BEFORE deleting our row —
    # otherwise Stripe keeps charging a customer record we no longer track.
    from app.models import Subscription
    sub_row = (
        await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
    ).scalar_one_or_none()
    if sub_row is not None and sub_row.stripe_subscription_id:
        try:
            from app.services.stripe_billing import _stripe
            stripe = _stripe()
            stripe.Subscription.delete(sub_row.stripe_subscription_id)
            logger.info(
                "stripe-cancel-on-purge: canceled %s", sub_row.stripe_subscription_id
            )
        except Exception as e:
            logger.warning("stripe-cancel-on-purge failed: %s", e)
            # Don't block: user's right to erasure trumps our billing
            # bookkeeping. We can clean up the Stripe customer manually.

    owned_ws = await _user_owned_workspace_ids(session, user_id)

    # Reject if any owned workspace has co-members.
    for ws_id in owned_ws:
        co_member_count = await session.scalar(
            select(WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == ws_id)
            .where(WorkspaceMember.user_id != user_id)
            .limit(1)
        )
        if co_member_count is not None:
            ws = (
                await session.execute(select(Workspace).where(Workspace.id == ws_id))
            ).scalar_one()
            raise ConflictError(
                detail=(
                    f"You own workspace '{ws.slug}' which has other members. "
                    "Transfer ownership or remove members first, then retry."
                )
            )

    # Delete owned workspaces — Postgres cascades through projects, project_*,
    # active_projects, audit_log, workspace_members, workspace_keys, ideas.
    if owned_ws:
        await session.execute(
            delete(Workspace).where(Workspace.id.in_(owned_ws))
        )

    # Delete user. Cascades through:
    #   workspace_members (CASCADE) — for any non-owned ws the user joined
    #   cli_devices (CASCADE)
    #   email_change_tokens (CASCADE)
    # MagicLinkToken is keyed by email, not user_id, so we clean explicitly:
    await session.execute(
        delete(MagicLinkToken).where(MagicLinkToken.email == user_row.email)
    )
    await session.execute(delete(User).where(User.id == user_id))
