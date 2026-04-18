import pytest

from app.core.session import (
    SessionPayload,
    create_session,
    delete_session,
    get_session,
)

pytestmark = pytest.mark.integration


async def test_create_then_get_roundtrip() -> None:
    session_id = await create_session(
        SessionPayload(user_id="01USER", workspace_id="01WS"), ttl_seconds=60,
    )
    assert isinstance(session_id, str)
    assert len(session_id) == 26

    payload = await get_session(session_id)
    assert payload is not None
    assert payload.user_id == "01USER"
    assert payload.workspace_id == "01WS"

    await delete_session(session_id)
    assert await get_session(session_id) is None


async def test_get_returns_none_for_missing() -> None:
    assert await get_session("01NOTEXIST" + "0" * 16) is None


async def test_expired_session_returns_none() -> None:
    import asyncio
    session_id = await create_session(
        SessionPayload(user_id="u", workspace_id="w"), ttl_seconds=1,
    )
    await asyncio.sleep(1.2)
    assert await get_session(session_id) is None
