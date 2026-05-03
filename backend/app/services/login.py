"""Magic-link token issuance and verification + first-login workspace bootstrap."""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import generate_dek, wrap_dek
from app.core.errors import UnauthorizedError, ValidationError
from app.core.session import SessionPayload, create_session
from app.core.ulid import new_ulid
from app.models import (
    MagicLinkToken,
    Plan,
    Subscription,
    User,
    Workspace,
    WorkspaceKey,
    WorkspaceMember,
)

_MAGIC_LINK_TTL_MINUTES = 15
_SLUG_RE = re.compile(r"[^a-z0-9-]")


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def issue_magic_link(session: AsyncSession, *, email: str) -> str:
    """Create a magic-link token for `email` and return the RAW token (caller sends it in URL)."""
    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    expires_at = datetime.now(UTC) + timedelta(minutes=_MAGIC_LINK_TTL_MINUTES)

    session.add(MagicLinkToken(
        id=new_ulid(),
        email=email.strip().lower(),
        token_hash=token_hash,
        expires_at=expires_at,
    ))
    await session.flush()
    return raw


def _derive_workspace_slug(email: str) -> str:
    """Deterministic default-workspace slug from email local-part."""
    local = email.split("@", 1)[0].lower()
    slug = _SLUG_RE.sub("-", local)[:20].strip("-")
    if not slug:
        slug = "ws"
    return slug


async def _unique_slug(session: AsyncSession, desired: str) -> str:
    """Append -2, -3, ... if `desired` is taken."""
    slug = desired
    suffix = 1
    while True:
        result = await session.execute(select(Workspace.id).where(Workspace.slug == slug))
        if result.first() is None:
            return slug
        suffix += 1
        slug = f"{desired}-{suffix}"
        if len(slug) > 50:
            slug = slug[:50]


async def login_or_bootstrap_user(
    session: AsyncSession, *, email: str
) -> tuple[User, Workspace]:
    """Find user by email, or create user + workspace + DEK + trial subscription.

    Shared by magic-link verify AND OAuth providers (Google, etc.) — anyone
    who can prove they own `email` arrives here. Idempotent for existing
    users (no subscription dup, no workspace dup). On first login: creates
    User + Workspace + WorkspaceMember(owner) + WorkspaceKey + 7-day
    trialing Subscription on the default `pro` plan. Caller is responsible
    for marking email_verified_at + creating the session cookie.
    """
    email = email.strip().lower()
    user_result = await session.execute(select(User).where(User.email == email))
    existing_user = user_result.scalar_one_or_none()

    if existing_user is not None:
        ws_result = await session.execute(
            select(Workspace).where(Workspace.owner_id == existing_user.id).limit(1)
        )
        existing_workspace = ws_result.scalar_one_or_none()
        if existing_workspace is None:
            raise UnauthorizedError(detail="user has no workspace")
        return existing_user, existing_workspace

    # First-login bootstrap
    user = User(id=new_ulid(), email=email)
    session.add(user)
    await session.flush()

    desired_slug = _derive_workspace_slug(email)
    slug = await _unique_slug(session, desired_slug)
    workspace: Workspace = Workspace(
        id=new_ulid(),
        slug=slug,
        name=desired_slug.replace("-", " ").title() or "Default",
        owner_id=user.id,
    )
    session.add(workspace)
    await session.flush()

    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))

    dek = generate_dek()
    wrapped = wrap_dek(dek, master_key_b64=get_settings().master_key)
    session.add(WorkspaceKey(workspace_id=workspace.id, dek_ciphertext=wrapped))
    await session.flush()

    # Spec-6 B1: bootstrap a Subscription row pointing at the default plan
    # (pro), status=trialing with trial_ends_at set per plan. Stripe linkage
    # is filled in later when the user actually goes through Checkout.
    default_plan = (
        await session.execute(select(Plan).where(Plan.slug == "pro"))
    ).scalar_one_or_none()
    if default_plan is not None:
        now = datetime.now(UTC)
        session.add(
            Subscription(
                id=new_ulid(),
                user_id=user.id,
                plan_id=default_plan.id,
                status="trialing",
                trial_ends_at=now + timedelta(days=default_plan.trial_period_days),
            )
        )
        await session.flush()

    return user, workspace


async def verify_magic_link(session: AsyncSession, *, raw_token: str) -> str:
    """Consume a raw magic-link token and return a session_id (creating user/workspace on first login)."""
    if not raw_token or len(raw_token) < 20:
        raise ValidationError(detail="invalid token")

    token_hash = _hash_token(raw_token)
    result = await session.execute(
        select(MagicLinkToken).where(MagicLinkToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise UnauthorizedError(detail="invalid or already-used link")
    if token.consumed_at is not None:
        raise UnauthorizedError(detail="link already used")
    if token.expires_at < datetime.now(UTC):
        raise UnauthorizedError(detail="link expired")

    user, workspace = await login_or_bootstrap_user(session, email=token.email)

    # Mark token consumed
    token.consumed_at = datetime.now(UTC)

    # Magic-link IS email verification: clicking the link proves mailbox
    # control. Record that fact on first verify (idempotent — only writes
    # the first time to preserve the original verification timestamp).
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)

    await session.flush()

    session_id = await create_session(
        SessionPayload(user_id=user.id, workspace_id=workspace.id),
        ttl_seconds=get_settings().session_max_age,
    )
    return session_id
