import pytest

from app.core.redis import get_redis

pytestmark = pytest.mark.integration


async def test_ping_and_set_get() -> None:
    r = await get_redis()
    assert await r.ping() is True

    await r.set("hangar-test-key", "value", ex=10)
    val = await r.get("hangar-test-key")
    assert val == "value"

    await r.delete("hangar-test-key")


async def test_get_redis_returns_singleton() -> None:
    r1 = await get_redis()
    r2 = await get_redis()
    assert r1 is r2
