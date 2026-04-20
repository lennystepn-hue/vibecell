"""Ephemeral consent state — state → validated authorize params (Redis, TTL 10m)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from app.core.redis import get_redis

_PREFIX = "oauth:consent:"
_TTL = 600


@dataclass(frozen=True, slots=True)
class ConsentState:
    client_id: str
    redirect_uri: str
    code_challenge: str
    scope: str
    state: str
    user_id: str


async def store(cs: ConsentState) -> None:
    r = await get_redis()
    await r.set(f"{_PREFIX}{cs.state}", json.dumps(asdict(cs)), ex=_TTL)


async def fetch(state: str) -> ConsentState | None:
    r = await get_redis()
    raw = await r.get(f"{_PREFIX}{state}")
    if raw is None:
        return None
    return ConsentState(**json.loads(raw))


async def drop(state: str) -> None:
    r = await get_redis()
    await r.delete(f"{_PREFIX}{state}")
