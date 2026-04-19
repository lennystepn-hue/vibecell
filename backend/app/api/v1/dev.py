"""Dev-mode-only helpers for E2E tests.

All routes are gated on HANGAR_DEV_MODE=1. Never enable in production.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import HangarError, NotFoundError
from app.models import MagicLinkToken

router = APIRouter(prefix="/api/v1/test", tags=["_dev"])


def _require_dev() -> None:
    if not get_settings().dev_mode:
        raise HangarError(
            title="Dev endpoint disabled",
            status=404,
            type_="/errors/not-found",
            detail="dev mode not enabled",
        )


@router.get("/magic-link-token")
async def latest_magic_link_token(
    email: Annotated[str, Query(min_length=3)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Return the RAW token for the most-recent unconsumed magic-link for `email`.

    Note: we only store the hash, not the raw token. So this route can't return
    the token — it returns the token_hash instead, and the E2E fixture uses a
    different strategy: it POSTs /auth/magic-link, then reads the backend logs
    where the dev-mode mailer printed the full verify_url.

    For now, we return the hash so the test can at least confirm the token was
    issued. Real E2E is gated on another mechanism (see Task 16.4 — direct DB
    seeding via SQL).
    """
    _require_dev()
    token = (await db.execute(
        select(MagicLinkToken)
        .where(MagicLinkToken.email == email.lower(), MagicLinkToken.consumed_at.is_(None))
        .order_by(MagicLinkToken.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if token is None:
        raise NotFoundError("magic_link_token", email)
    # We can't recover the raw token from the hash. Dev-only workaround:
    # issue a fresh token here and return it.
    import secrets
    import hashlib
    from datetime import UTC, datetime, timedelta
    from app.core.ulid import new_ulid

    raw = secrets.token_urlsafe(32)
    from app.models import MagicLinkToken as _Token
    new = _Token(
        id=new_ulid(),
        email=email.lower(),
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    db.add(new)
    await db.commit()
    return {"token": raw}
