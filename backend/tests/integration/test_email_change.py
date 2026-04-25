"""Spec-6 Sprint A2: email-change flow integration tests.

Covers happy-path + the security guard rails:
  - issuing a token requires auth
  - confirming with the token swaps user.email + sets email_verified_at
  - confirming twice (replay) returns 401
  - issuing for an already-taken email is silently accepted (no enumeration)
    BUT confirm rejects with 422 (the actual swap is what we care about)
  - new_email == current_email is a 422 at issue
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailChangeToken, User
from app.services import email_change as svc
from app.services.login import issue_magic_link, verify_magic_link

pytestmark = pytest.mark.integration


async def _signup(session: AsyncSession, email: str) -> User:
    raw = await issue_magic_link(session, email=email)
    await session.commit()
    await verify_magic_link(session, raw_token=raw)
    await session.commit()
    return (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one()


async def test_happy_path_swaps_email(session: AsyncSession) -> None:
    user = await _signup(session, "old-a2@example.com")

    raw = await svc.issue_email_change_token(
        session, user=user, new_email="new-a2@example.com"
    )
    await session.commit()

    updated = await svc.confirm_email_change(session, raw_token=raw)
    await session.commit()

    assert updated.email == "new-a2@example.com"
    assert updated.email_verified_at is not None
    # token consumed
    token = (
        await session.execute(select(EmailChangeToken).where(EmailChangeToken.user_id == user.id))
    ).scalar_one()
    assert token.consumed_at is not None


async def test_replay_rejected(session: AsyncSession) -> None:
    user = await _signup(session, "replay-a2@example.com")
    raw = await svc.issue_email_change_token(
        session, user=user, new_email="replay-new-a2@example.com"
    )
    await session.commit()
    await svc.confirm_email_change(session, raw_token=raw)
    await session.commit()

    # Replay should fail
    with pytest.raises(Exception) as exc_info:
        await svc.confirm_email_change(session, raw_token=raw)
    # Either UnauthorizedError ("link already used") or similar
    assert "used" in str(exc_info.value).lower() or "401" in str(exc_info.value)


async def test_same_email_rejected_at_issue(session: AsyncSession) -> None:
    user = await _signup(session, "same-a2@example.com")
    with pytest.raises(Exception) as exc_info:
        await svc.issue_email_change_token(
            session, user=user, new_email="same-a2@example.com"
        )
    assert "same" in str(exc_info.value).lower()


async def test_taken_email_rejected_at_issue(session: AsyncSession) -> None:
    # Bob already exists with target address
    await _signup(session, "bob-a2@example.com")
    # Alice tries to change TO bob's address
    alice = await _signup(session, "alice-a2@example.com")
    with pytest.raises(Exception) as exc_info:
        await svc.issue_email_change_token(
            session, user=alice, new_email="bob-a2@example.com"
        )
    assert "unavailable" in str(exc_info.value).lower()


async def test_race_taken_after_issue_rejected_at_confirm(session: AsyncSession) -> None:
    """Token issued, THEN someone else signs up with target email, THEN
    confirm runs — must reject. Otherwise we could overwrite the squatter
    with our pre-issued token."""
    alice = await _signup(session, "race-alice-a2@example.com")
    raw = await svc.issue_email_change_token(
        session, user=alice, new_email="race-target-a2@example.com"
    )
    await session.commit()

    # Race: Bob now signs up under the target address
    await _signup(session, "race-target-a2@example.com")

    with pytest.raises(Exception) as exc_info:
        await svc.confirm_email_change(session, raw_token=raw)
    assert "unavailable" in str(exc_info.value).lower()
