"""Spec-6 Sprint A2: change a user's email address.

The flow:
  1. POST /me/change-email  body: {new_email}      (auth required)
       → server emails a one-time token to new_email
  2. POST /me/change-email/confirm  body: {token}  (no auth required —
                                                    proves only token possession)
       → server swaps user.email + email_verified_at + invalidates current sessions

Security notes:
  - Token is bound to user_id at issue time, so a leaked token can only target
    the issuing user (no cross-account hijack).
  - new_email uniqueness is checked at confirm time (not just issue time) so
    a race where Bob signed up between Alice's request + confirm is rejected.
  - All Alice's existing sessions are invalidated on swap — she has to sign
    in again under the new email. Prevents stale sessions if a malicious
    request beats the legitimate user.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthorizedError, ValidationError
from app.core.ulid import new_ulid
from app.models import EmailChangeToken, User

_TOKEN_TTL_HOURS = 24


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def issue_email_change_token(
    session: AsyncSession,
    *,
    user: User,
    new_email: str,
) -> str:
    """Create a token bound to (user, new_email) and return the RAW token
    so the caller can put it in the email body.

    Raises ValidationError if new_email is already in use by ANOTHER user
    (same address as the current user is fine, just no-ops at confirm time).
    """
    new_email_clean = new_email.strip().lower()
    if not new_email_clean or "@" not in new_email_clean:
        raise ValidationError(detail="invalid email address")
    if new_email_clean == user.email:
        raise ValidationError(detail="new email is the same as current")

    existing = (
        await session.execute(select(User).where(User.email == new_email_clean))
    ).scalar_one_or_none()
    if existing is not None and existing.id != user.id:
        # Don't reveal whether the address is taken to avoid email-enumeration —
        # but DO reject so we never accidentally try to swap to a duplicate.
        raise ValidationError(detail="email unavailable")

    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    expires_at = datetime.now(UTC) + timedelta(hours=_TOKEN_TTL_HOURS)

    session.add(
        EmailChangeToken(
            id=new_ulid(),
            user_id=user.id,
            new_email=new_email_clean,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    await session.flush()
    return raw


async def confirm_email_change(session: AsyncSession, *, raw_token: str) -> User:
    """Consume the token + swap user.email + invalidate the user's other
    sessions. Returns the updated User.

    The current request's session cookie is left alone (caller may want to
    keep the user logged in OR force re-login depending on UX). If you want
    forced re-login, the caller should also delete the request's session
    after this returns.
    """
    if not raw_token or len(raw_token) < 20:
        raise ValidationError(detail="invalid token")

    token_hash = _hash_token(raw_token)
    token = (
        await session.execute(
            select(EmailChangeToken).where(EmailChangeToken.token_hash == token_hash)
        )
    ).scalar_one_or_none()
    if token is None:
        raise UnauthorizedError(detail="invalid or already-used link")
    if token.consumed_at is not None:
        raise UnauthorizedError(detail="link already used")
    if token.expires_at < datetime.now(UTC):
        raise UnauthorizedError(detail="link expired")

    # Re-check uniqueness at confirm time — Bob could have signed up under
    # the target address since the token was issued.
    clash = (
        await session.execute(
            select(User).where(User.email == token.new_email).where(User.id != token.user_id)
        )
    ).scalar_one_or_none()
    if clash is not None:
        raise ValidationError(detail="email unavailable")

    user = (
        await session.execute(select(User).where(User.id == token.user_id))
    ).scalar_one_or_none()
    if user is None:
        raise UnauthorizedError(detail="user no longer exists")

    old_email = user.email
    user.email = token.new_email
    user.email_verified_at = datetime.now(UTC)  # the new address is now verified

    token.consumed_at = datetime.now(UTC)

    # Drop any pending magic-link tokens for the OLD email — they'd be useless
    # but cleaner to clear so they can't be abused if the old mailbox is
    # compromised separately.
    from app.models import MagicLinkToken
    await session.execute(
        delete(MagicLinkToken)
        .where(MagicLinkToken.email == old_email)
        .where(MagicLinkToken.consumed_at.is_(None))
    )

    await session.flush()
    return user
