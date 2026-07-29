"""One-time pairing codes for the one-line installer.

The existing device-code flow in `services/cli_pair.py` assumes the CLI
starts the conversation and the *browser* confirms. Onboarding is the other
way round: the user is already signed in in the browser, and we want the
script they paste into a terminal to reach a device token without sending
them back to the browser to approve something they just asked for.

So: the browser mints a code, the code is baked into the one-liner, and the
installer redeems it exactly once.

Redis keys:
  onboarding-code:{code} → JSON {user_id, workspace_id}   TTL 10 min

Security shape, and why:

  * **Single-use.** This is the real protection. The code lands in the user's
    shell history the moment they paste the line; by the time anyone reads it
    there, the installer has already spent it.
  * **10 minutes.** The window only bounds shoulder-surfing, so it is sized
    for a human copying a line into a terminal — including opening one first.
    60 seconds was considered and rejected: it expires mid-paste.
  * **Device pairing only.** Redeeming produces a `CliDevice` row and nothing
    else. The code is not a session, cannot read a project, and the only
    endpoint that accepts it creates a device. What it produces is revocable
    from Settings via the existing `DELETE /api/v1/cli/devices/{id}`.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from secrets import SystemRandom

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.redis import get_redis
from app.core.ulid import new_ulid
from app.models import CliDevice, Workspace

# Same Crockford-ish alphabet as the device-code flow: no 0/O/I/1/L/U, so a
# code read off a screen and typed by hand can't land on the wrong character.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"
_CODE_LEN = 8  # 30^8 ≈ 6.6e11 — unguessable inside a 10-minute single-use window
_TTL_SECONDS = 600

_rng = SystemRandom()


def _key(code: str) -> str:
    return f"onboarding-code:{code}"


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def gen_code() -> str:
    return "".join(_rng.choice(_CODE_ALPHABET) for _ in range(_CODE_LEN))


async def issue_code(*, user_id: str, workspace_id: str) -> tuple[str, int]:
    """Mint a fresh code bound to this user. Returns (code, ttl_seconds)."""
    redis = await get_redis()
    payload = json.dumps({"user_id": user_id, "workspace_id": workspace_id})
    for _ in range(5):
        code = gen_code()
        # nx so a collision with a live code can never overwrite it and hand
        # two people the same string.
        if await redis.set(_key(code), payload, nx=True, ex=_TTL_SECONDS):
            return code, _TTL_SECONDS
    raise RuntimeError("unable to allocate an onboarding code; retry")


async def code_exists(code: str) -> bool:
    """Non-consuming existence check.

    `/i/{code}` uses this so a dead link renders an explanation instead of a
    script that will fail confusingly halfway through an install. It must not
    consume: the installer still needs the code afterwards.
    """
    redis = await get_redis()
    return bool(await redis.exists(_key(code)))


async def redeem_code(
    db: AsyncSession,
    *,
    code: str,
    device_name: str | None,
) -> dict[str, str]:
    """Spend the code and return a device bearer token.

    The consume is atomic (`GETDEL`), so two installers racing on the same
    code cannot both walk away with a device — exactly one wins and the other
    sees a dead code.
    """
    redis = await get_redis()
    raw = await redis.getdel(_key(code))
    if raw is None:
        raise NotFoundError("onboarding code", code)

    payload = json.loads(raw)
    user_id: str = payload["user_id"]
    workspace_id: str = payload["workspace_id"]

    ws = (
        await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ).scalar_one_or_none()
    if ws is None:
        raise NotFoundError("workspace", workspace_id)

    token = secrets.token_urlsafe(32)
    device_id = new_ulid()
    db.add(
        CliDevice(
            id=device_id,
            user_id=user_id,
            name=device_name,
            paired_at=datetime.now(UTC),
            token_hash=_hash_token(token),
        )
    )
    await db.flush()

    return {
        "token": token,
        "device_id": device_id,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "workspace_slug": ws.slug,
    }
