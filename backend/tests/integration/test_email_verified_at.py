"""Spec-6 Sprint A1: email_verified_at is set when magic-link is consumed.

Magic-link auth IS email verification — clicking the link proves mailbox
control. The User.email_verified_at column captures this fact for downstream
consumers (Stripe customer creation, support tooling, email-change flows).

These tests cover:
  - first verify sets the timestamp
  - second verify does NOT overwrite the timestamp (idempotent)
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services.login import issue_magic_link, verify_magic_link

pytestmark = pytest.mark.integration


async def test_first_verify_sets_email_verified_at(session: AsyncSession) -> None:
    raw = await issue_magic_link(session, email="newuser-a1@example.com")
    await session.commit()

    await verify_magic_link(session, raw_token=raw)
    await session.commit()

    user = (
        await session.execute(
            select(User).where(User.email == "newuser-a1@example.com")
        )
    ).scalar_one()

    assert user.email_verified_at is not None, (
        "first magic-link consume must record email_verified_at"
    )


async def test_second_verify_does_not_overwrite(session: AsyncSession) -> None:
    # First sign-in
    raw1 = await issue_magic_link(session, email="repeat-a1@example.com")
    await session.commit()
    await verify_magic_link(session, raw_token=raw1)
    await session.commit()

    user = (
        await session.execute(
            select(User).where(User.email == "repeat-a1@example.com")
        )
    ).scalar_one()
    first_verified_at = user.email_verified_at
    assert first_verified_at is not None

    # Second sign-in
    raw2 = await issue_magic_link(session, email="repeat-a1@example.com")
    await session.commit()
    await verify_magic_link(session, raw_token=raw2)
    await session.commit()

    await session.refresh(user)
    assert user.email_verified_at == first_verified_at, (
        "subsequent verifies must preserve the original verification timestamp"
    )
