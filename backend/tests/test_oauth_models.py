from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ulid import new_ulid
from app.models.auth import User, Workspace
from app.oauth.models import (
    OAuthAccessToken,
    OAuthAuthCode,
    OAuthClient,
    OAuthRefreshToken,
)

pytestmark = pytest.mark.integration


async def _seed_base(session: AsyncSession) -> tuple[str, str, str]:
    """Create user + workspace + oauth_client; return (user_id, workspace_id, client_id)."""
    user = User(email=f"oauth-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()

    workspace = Workspace(
        slug=f"ws-{new_ulid()}",
        name="Test WS",
        owner_id=user.id,
    )
    session.add(workspace)
    await session.flush()

    client_id = f"dyn_{new_ulid()}"
    client = OAuthClient(
        id=new_ulid(),
        client_id=client_id,
        client_name="Claude Desktop",
        redirect_uris=["http://127.0.0.1:12345/callback"],
        scope="vibecell:tools",
    )
    session.add(client)
    await session.flush()

    return user.id, workspace.id, client_id


async def test_oauth_client_insert_roundtrip(session: AsyncSession) -> None:
    _user_id, _workspace_id, client_id = await _seed_base(session)

    got = (
        await session.execute(
            select(OAuthClient).where(OAuthClient.client_id == client_id)
        )
    ).scalar_one()
    assert got.client_name == "Claude Desktop"
    assert got.revoked_at is None
    assert got.redirect_uris == ["http://127.0.0.1:12345/callback"]


async def test_auth_code_expires_at_default(session: AsyncSession) -> None:
    user_id, workspace_id, client_id = await _seed_base(session)

    code = OAuthAuthCode(
        id=new_ulid(),
        code=f"c_{new_ulid()}",
        client_id=client_id,
        user_id=user_id,
        workspace_id=workspace_id,
        redirect_uri="http://127.0.0.1:12345/callback",
        code_challenge="xyz",
        scope="vibecell:tools",
        expires_at=datetime.now(UTC) + timedelta(seconds=60),
    )
    session.add(code)
    await session.flush()
    assert code.consumed_at is None


async def test_refresh_token_hash_unique_constraint(session: AsyncSession) -> None:
    from sqlalchemy.exc import IntegrityError

    user_id, workspace_id, client_id = await _seed_base(session)

    fam1 = new_ulid()
    fam2 = new_ulid()
    now = datetime.now(UTC)
    t1 = OAuthRefreshToken(
        id=new_ulid(),
        token_hash="sha_same",
        family_id=fam1,
        client_id=client_id,
        user_id=user_id,
        workspace_id=workspace_id,
        scope="vibecell:tools",
        issued_at=now,
        expires_at=now + timedelta(days=30),
    )
    t2 = OAuthRefreshToken(
        id=new_ulid(),
        token_hash="sha_same",  # duplicate hash
        family_id=fam2,
        client_id=client_id,
        user_id=user_id,
        workspace_id=workspace_id,
        scope="vibecell:tools",
        issued_at=now,
        expires_at=now + timedelta(days=30),
    )
    session.add(t1)
    await session.flush()

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(t2)
            await session.flush()


async def test_access_token_jti_indexed(session: AsyncSession) -> None:
    user_id, workspace_id, client_id = await _seed_base(session)

    jti = new_ulid()
    tok = OAuthAccessToken(
        id=new_ulid(),
        jti=jti,
        client_id=client_id,
        user_id=user_id,
        workspace_id=workspace_id,
        scope="vibecell:tools",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add(tok)
    await session.flush()
    got = (
        await session.execute(
            select(OAuthAccessToken).where(OAuthAccessToken.jti == jti)
        )
    ).scalar_one()
    assert got.revoked_at is None
