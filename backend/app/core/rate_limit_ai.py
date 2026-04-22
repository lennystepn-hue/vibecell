"""Redis-backed sliding-window rate limiter for AI endpoints.

Protects users (and us) from runaway Anthropic bills if an endpoint gets
hit in a tight loop — accidentally from a frontend bug or maliciously.

Default bucket: 20 AI calls / hour per (user_id, project_id) pair. Easy to
override per-endpoint via the `bucket_limit` argument. Falls back to allow
if Redis is unreachable so a broken Redis never hard-stops user flow (the
AI call might then be blocked by Anthropic itself or cost a little extra).
"""
from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.deps import AuthContext, ProjectContext, require_auth, require_project
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

DEFAULT_BUCKET_LIMIT = 20        # calls
DEFAULT_WINDOW_SECONDS = 3600    # 1 hour
KEY_TMPL = "vc:ratelimit:ai:{user_id}:{project_id}"


async def _check_sliding_window(
    *, key: str, limit: int, window_seconds: int,
) -> tuple[bool, int, float]:
    """Return (allowed, count_in_window, oldest_ts_seconds).

    Implementation: Redis sorted-set sliding window. Each call appends a
    timestamp, old entries (outside the window) get trimmed on read. We
    pipeline both operations + TTL to keep this to 3 round-trips per call.
    """
    now = time.time()
    window_start = now - window_seconds
    try:
        r = await get_redis()
        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        res = await pipe.execute()
        count = int(res[1] or 0)
        if count >= limit:
            oldest = await r.zrange(key, 0, 0, withscores=True)
            oldest_ts = float(oldest[0][1]) if oldest else now
            return False, count, oldest_ts
        pipe = r.pipeline()
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds + 60)
        await pipe.execute()
        return True, count + 1, now
    except Exception:  # noqa: BLE001
        logger.warning("ai rate-limit redis failure — fail-open", exc_info=True)
        return True, 0, now


async def enforce_ai_rate_limit(
    auth: Annotated[AuthContext, Depends(require_auth)],
    ctx: Annotated[ProjectContext, Depends(require_project)],
) -> None:
    """FastAPI dependency for AI routes. Raises 429 when bucket exhausted."""
    key = KEY_TMPL.format(user_id=auth.user.id, project_id=ctx.project.id)
    allowed, count, oldest_ts = await _check_sliding_window(
        key=key,
        limit=DEFAULT_BUCKET_LIMIT,
        window_seconds=DEFAULT_WINDOW_SECONDS,
    )
    if allowed:
        return
    retry_after = max(1, int((oldest_ts + DEFAULT_WINDOW_SECONDS) - time.time()))
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=(
            f"AI rate limit: {DEFAULT_BUCKET_LIMIT} calls/hour per project. "
            f"{count} used in the last hour. Try again in {retry_after}s."
        ),
        headers={"Retry-After": str(retry_after)},
    )
