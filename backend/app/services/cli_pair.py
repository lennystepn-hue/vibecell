"""Service layer for the CLI device-code pairing flow.

Redis keys:
  pair-start:{device_code}  → JSON {user_code, device_name:null}        TTL 10 min
  pair-code:{user_code}     → JSON {device_code}                        TTL 10 min
  pair-ready:{device_code}  → JSON {token, device_id, user_id,
                                     workspace_id, workspace_slug}      TTL 60 s
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from secrets import SystemRandom

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.core.redis import get_redis
from app.core.ulid import new_ulid
from app.models import CliDevice, Workspace
from app.schemas.cli import PairCompleteResponse, PairStartResponse

# Crockford-ish alphabet: no 0/O/I/1/L/U to avoid ambiguity when typing.
_USER_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"
_USER_CODE_LEN = 8  # rendered as XXXX-XXXX (4+4)
_EXPIRES_IN_SECONDS = 600  # 10 minutes
_READY_TTL_SECONDS = 60  # short — picked up within one poll cycle

_rng = SystemRandom()


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _gen_user_code() -> str:
    chars = [_rng.choice(_USER_CODE_ALPHABET) for _ in range(_USER_CODE_LEN)]
    return f"{''.join(chars[:4])}-{''.join(chars[4:])}"


def _gen_device_code() -> str:
    return secrets.token_urlsafe(32)


async def start_pairing() -> PairStartResponse:
    """Generate a new device_code + user_code and stash both in Redis."""
    redis = await get_redis()

    # Regenerate in the rare case of a user_code collision.
    device_code = _gen_device_code()
    for _ in range(5):
        user_code = _gen_user_code()
        # Atomic reserve using SETNX equivalent.
        ok = await redis.set(
            f"pair-code:{user_code}",
            json.dumps({"device_code": device_code}),
            nx=True,
            ex=_EXPIRES_IN_SECONDS,
        )
        if ok:
            break
    else:
        raise ValidationError(detail="unable to allocate a user_code; retry")

    await redis.set(
        f"pair-start:{device_code}",
        json.dumps({"user_code": user_code, "device_name": None}),
        ex=_EXPIRES_IN_SECONDS,
    )

    base_url = get_settings().base_url.rstrip("/")
    return PairStartResponse(
        device_code=device_code,
        user_code=user_code,
        verification_url=f"{base_url}/cli/pair",
        expires_in=_EXPIRES_IN_SECONDS,
    )


async def confirm_pairing(
    db: AsyncSession,
    *,
    user_id: str,
    workspace_id: str,
    user_code: str,
    device_name: str | None,
) -> None:
    """Browser-side confirm: user is signed-in and pastes the user_code.

    Creates the cli_devices row + stashes `pair-ready:{device_code}`.
    """
    redis = await get_redis()

    raw = await redis.get(f"pair-code:{user_code}")
    if raw is None:
        raise NotFoundError("pairing code", user_code)
    payload = json.loads(raw)
    device_code = payload["device_code"]

    # Resolve workspace slug for the response.
    ws = (await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )).scalar_one_or_none()
    if ws is None:
        raise NotFoundError("workspace", workspace_id)

    # Generate bearer token — raw goes to CLI, sha256 to DB.
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    device_id = new_ulid()
    db.add(CliDevice(
        id=device_id,
        user_id=user_id,
        name=device_name,
        paired_at=datetime.now(UTC),
        token_hash=token_hash,
    ))
    await db.flush()

    ready_payload = {
        "token": token,
        "device_id": device_id,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "workspace_slug": ws.slug,
    }
    await redis.set(
        f"pair-ready:{device_code}",
        json.dumps(ready_payload),
        ex=_READY_TTL_SECONDS,
    )
    await redis.delete(f"pair-start:{device_code}")
    await redis.delete(f"pair-code:{user_code}")


async def complete_pairing(device_code: str) -> PairCompleteResponse | None:
    """Polling endpoint: if the browser has confirmed, return the token + delete the key."""
    redis = await get_redis()
    raw = await redis.get(f"pair-ready:{device_code}")
    if raw is None:
        return None
    payload = json.loads(raw)
    # Delete *before* returning so a race doesn't yield the token twice.
    await redis.delete(f"pair-ready:{device_code}")
    return PairCompleteResponse(**payload)


async def list_devices(db: AsyncSession, *, user_id: str) -> list[CliDevice]:
    rows = (await db.execute(
        select(CliDevice)
        .where(CliDevice.user_id == user_id)
        .order_by(CliDevice.paired_at.desc())
    )).scalars().all()
    return list(rows)


async def revoke_device(db: AsyncSession, *, user_id: str, device_id: str) -> None:
    existing = (await db.execute(
        select(CliDevice).where(CliDevice.id == device_id)
    )).scalar_one_or_none()
    if existing is None:
        raise NotFoundError("device", device_id)
    if existing.user_id != user_id:
        raise ForbiddenError(detail="not your device")
    await db.execute(delete(CliDevice).where(CliDevice.id == device_id))


async def find_device_by_token(db: AsyncSession, *, raw_token: str) -> CliDevice | None:
    """Bearer-token lookup used by the middleware. Returns None if not found."""
    token_hash = _hash_token(raw_token)
    return (await db.execute(
        select(CliDevice).where(CliDevice.token_hash == token_hash)
    )).scalar_one_or_none()


async def touch_device(db: AsyncSession, *, device_id: str) -> None:
    """Update last_seen_at. Fire-and-forget; caller commits."""
    existing = (await db.execute(
        select(CliDevice).where(CliDevice.id == device_id)
    )).scalar_one_or_none()
    if existing is not None:
        existing.last_seen_at = datetime.now(UTC)
