from __future__ import annotations

import asyncio

from redis.asyncio import Redis, from_url

from app.core.config import get_settings

_redis: Redis[str] | None = None
_lock = asyncio.Lock()


async def get_redis() -> Redis[str]:
    """Return a singleton async Redis client built from settings.redis_url."""
    global _redis
    if _redis is None:
        async with _lock:
            if _redis is None:
                _redis = from_url(
                    get_settings().redis_url,
                    decode_responses=True,
                    encoding="utf-8",
                )
    return _redis


async def close_redis() -> None:
    """Close the shared client and clear the singleton (call on app shutdown)."""
    global _redis
    if _redis is not None:
        await _redis.aclose()  # type: ignore[attr-defined]
        _redis = None
