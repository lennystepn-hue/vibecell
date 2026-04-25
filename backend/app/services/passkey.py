"""Passkey (WebAuthn) service — real registration + authentication.

Spec 4.2 — Launch-Enabler.
Uses the `webauthn` (py_webauthn) package.

Redis keys:
  passkey:reg:{user_id}   — registration challenge, TTL 5 min
  passkey:auth:{email}    — authentication challenge, TTL 5 min
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis
from app.core.session import SessionPayload, create_session
from app.models.auth import User, Workspace

logger = logging.getLogger(__name__)

_CHALLENGE_TTL = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _options_to_dict(opts: Any) -> dict[str, Any]:
    """Convert a py_webauthn options object to a JSON-serialisable dict.

    py_webauthn 2.x returns dataclass-like objects; `options_to_json()` gives
    us a JSON string of the camelCase representation the browser expects.
    """
    import webauthn

    return json.loads(webauthn.options_to_json(opts))


def _get_rp() -> tuple[str, str, str]:
    s = get_settings()
    return s.webauthn_rp_id, s.webauthn_rp_name, s.webauthn_origin


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def start_registration(user_id: str, user_email: str) -> dict[str, Any]:
    """Generate WebAuthn registration options for the frontend."""
    import webauthn
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )

    rp_id, rp_name, _ = _get_rp()

    # Load existing credentials to populate excludeCredentials
    async with _db_context() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        existing_creds: list[Any] = user.passkey_credentials if (user and user.passkey_credentials) else []

    exclude_credentials = []
    import base64

    from webauthn.helpers.structs import PublicKeyCredentialDescriptor
    for cred in existing_creds:
        raw_id = base64.urlsafe_b64decode(cred["credential_id"] + "==")
        exclude_credentials.append(PublicKeyCredentialDescriptor(id=raw_id))

    opts = webauthn.generate_registration_options(
        rp_id=rp_id,
        rp_name=rp_name,
        user_id=user_id.encode(),
        user_name=user_email,
        user_display_name=user_email,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    # Store challenge in Redis
    redis = await get_redis()
    challenge_b64 = _bytes_to_b64(opts.challenge)
    await redis.set(f"passkey:reg:{user_id}", challenge_b64, ex=_CHALLENGE_TTL)

    logger.info("passkey.start_registration user=%s", user_id)
    return _options_to_dict(opts)


async def finish_registration(
    user_id: str,
    credential_response: dict[str, Any],
) -> bool:
    """Verify registration response and persist new credential."""
    import webauthn
    from webauthn.helpers.exceptions import InvalidCBORData, InvalidRegistrationResponse

    rp_id, _, origin = _get_rp()

    # Fetch challenge from Redis
    redis = await get_redis()
    raw_challenge = await redis.get(f"passkey:reg:{user_id}")
    if not raw_challenge:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="registration_challenge_expired")

    expected_challenge = _b64_to_bytes(raw_challenge)

    try:
        verification = webauthn.verify_registration_response(
            credential=credential_response,
            expected_challenge=expected_challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
            require_user_verification=False,
        )
    except (InvalidRegistrationResponse, InvalidCBORData, Exception) as exc:
        logger.warning("passkey.finish_registration verification failed user=%s: %s", user_id, exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="registration_failed") from exc

    # Delete the used challenge
    await redis.delete(f"passkey:reg:{user_id}")

    # Persist credential to user.passkey_credentials JSONB list
    import base64
    new_cred = {
        "credential_id": base64.urlsafe_b64encode(verification.credential_id).decode().rstrip("="),
        "public_key": base64.urlsafe_b64encode(verification.credential_public_key).decode().rstrip("="),
        "sign_count": verification.sign_count,
        "transports": [],
        "registered_at": datetime.now(UTC).isoformat(),
    }

    async with _db_context() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
        creds = list(user.passkey_credentials or [])
        creds.append(new_cred)
        user.passkey_credentials = creds

    logger.info("passkey.finish_registration ok user=%s cred_id=%s", user_id, new_cred["credential_id"][:12])
    return True


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def start_authentication(email: str) -> dict[str, Any]:
    """Generate WebAuthn authentication options for the frontend."""
    import base64

    import webauthn
    from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement

    rp_id, _, _ = _get_rp()

    async with _db_context() as db:
        user = (await db.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()

    if user is None or not user.passkey_credentials:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no_passkeys_registered")

    allow_credentials = [
        PublicKeyCredentialDescriptor(
            id=base64.urlsafe_b64decode(c["credential_id"] + "=="),
        )
        for c in user.passkey_credentials
    ]

    opts = webauthn.generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    redis = await get_redis()
    await redis.set(f"passkey:auth:{email.lower()}", _bytes_to_b64(opts.challenge), ex=_CHALLENGE_TTL)

    logger.info("passkey.start_authentication email=%s", email)
    return _options_to_dict(opts)


async def finish_authentication(
    email: str,
    assertion_response: dict[str, Any],
) -> str:
    """Verify authentication assertion and return a new session_id."""
    import base64

    import webauthn
    from webauthn.helpers.exceptions import InvalidAuthenticationResponse

    rp_id, _, origin = _get_rp()

    redis = await get_redis()
    raw_challenge = await redis.get(f"passkey:auth:{email.lower()}")
    if not raw_challenge:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="authentication_challenge_expired")

    expected_challenge = _b64_to_bytes(raw_challenge)

    async with _db_context() as db:
        user = (await db.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()
        if user is None or not user.passkey_credentials:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no_passkeys_registered")

        # Find matching credential by credential_id
        # The assertion response contains 'id' (base64url credential_id)
        asserted_id = assertion_response.get("id", "")
        matched_cred = None
        matched_idx = -1
        for idx, c in enumerate(user.passkey_credentials):
            if c["credential_id"] == asserted_id or c["credential_id"].rstrip("=") == asserted_id.rstrip("="):
                matched_cred = c
                matched_idx = idx
                break

        if matched_cred is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="credential_not_found")

        pub_key_bytes = base64.urlsafe_b64decode(matched_cred["public_key"] + "==")

        try:
            verification = webauthn.verify_authentication_response(
                credential=assertion_response,
                expected_challenge=expected_challenge,
                expected_rp_id=rp_id,
                expected_origin=origin,
                credential_public_key=pub_key_bytes,
                credential_current_sign_count=matched_cred.get("sign_count", 0),
                require_user_verification=False,
            )
        except (InvalidAuthenticationResponse, Exception) as exc:
            logger.warning("passkey.finish_authentication failed email=%s: %s", email, exc)
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="authentication_failed") from exc

        # Delete used challenge
        await redis.delete(f"passkey:auth:{email.lower()}")

        # Update sign_count
        creds = list(user.passkey_credentials)
        creds[matched_idx] = {**matched_cred, "sign_count": verification.new_sign_count}
        user.passkey_credentials = creds

        # Resolve workspace for session payload
        ws = (await db.execute(
            select(Workspace).where(Workspace.owner_id == user.id).limit(1)
        )).scalar_one_or_none()
        if ws is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="user_has_no_workspace")

        user_id = user.id
        workspace_id = ws.id

    from app.core.config import get_settings as _gs
    session_id = await create_session(
        SessionPayload(user_id=user_id, workspace_id=workspace_id),
        ttl_seconds=_gs().session_max_age,
    )
    logger.info("passkey.finish_authentication ok email=%s", email)
    return session_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bytes_to_b64(b: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64_to_bytes(s: str) -> bytes:
    import base64
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


@asynccontextmanager
async def _db_context() -> AsyncIterator[AsyncSession]:
    """Thin wrapper so we don't repeat session_scope imports everywhere."""
    from app.core.db import session_scope
    async with session_scope() as db:
        yield db
