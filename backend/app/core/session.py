"""Redis-backed session store for web auth.

Sessions are ULIDs; values are JSON-encoded SessionPayload. TTL is the
session cookie Max-Age (default 30 days). Deletion on logout or when
verify detects replay/tampering.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from app.core.redis import get_redis
from app.core.ulid import new_ulid

_KEY_PREFIX = "session:"


@dataclass(frozen=True, slots=True)
class SessionPayload:
    user_id: str
    workspace_id: str


def _key(session_id: str) -> str:
    return f"{_KEY_PREFIX}{session_id}"


async def create_session(payload: SessionPayload, *, ttl_seconds: int) -> str:
    redis = await get_redis()
    session_id = new_ulid()
    await redis.set(_key(session_id), json.dumps(asdict(payload)), ex=ttl_seconds)
    return session_id


async def get_session(session_id: str) -> SessionPayload | None:
    if not session_id:
        return None
    redis = await get_redis()
    raw = await redis.get(_key(session_id))
    if raw is None:
        return None
    data = json.loads(raw)
    return SessionPayload(user_id=data["user_id"], workspace_id=data["workspace_id"])


async def delete_session(session_id: str) -> None:
    redis = await get_redis()
    await redis.delete(_key(session_id))
