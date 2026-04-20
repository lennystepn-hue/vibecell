"""Passkey (WebAuthn) service — registration + authentication flows.

Status: STUB — real webauthn library integration deferred to Spec 4.2.
All four flow functions are defined with correct signatures and return
{"error": "not_implemented"} with HTTP 501 until the library is wired.

Future implementation uses the `webauthn` (py_webauthn) package:
  uv add webauthn

Environment variables needed:
  WEBAUTHN_RP_ID     e.g. vibecell.dev
  WEBAUTHN_RP_NAME   e.g. Vibecell
  WEBAUTHN_ORIGIN    e.g. https://vibecell.dev
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def start_registration(user_id: str, user_email: str) -> dict[str, Any]:
    """Generate WebAuthn registration options for the frontend.

    Full impl:
    1. Load existing credentials from user.passkey_credentials (exclude list).
    2. Call webauthn.generate_registration_options() with rpId, user, challenge.
    3. Store challenge in Redis with TTL=300 keyed on user_id.
    4. Return options JSON for navigator.credentials.create().
    """
    logger.info("passkey.start_registration called user=%s [STUB]", user_id)
    return {"error": "not_implemented", "detail": "Passkey registration not yet configured"}


async def finish_registration(
    user_id: str,
    credential_response: dict[str, Any],
) -> dict[str, Any]:
    """Verify registration response and persist new credential.

    Full impl:
    1. Retrieve challenge from Redis.
    2. Call webauthn.verify_registration_response().
    3. Append verified credential to user.passkey_credentials JSONB list.
    4. Return {"ok": True, "credential_id": "..."}.
    """
    logger.info("passkey.finish_registration called user=%s [STUB]", user_id)
    return {"error": "not_implemented", "detail": "Passkey registration not yet configured"}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def start_authentication(email: str) -> dict[str, Any]:
    """Generate WebAuthn authentication options for the frontend.

    Full impl:
    1. Look up user by email, load their passkey_credentials.
    2. Call webauthn.generate_authentication_options() with allowCredentials.
    3. Store challenge in Redis keyed on email with TTL=300.
    4. Return options JSON for navigator.credentials.get().
    """
    logger.info("passkey.start_authentication called email=%s [STUB]", email)
    return {"error": "not_implemented", "detail": "Passkey authentication not yet configured"}


async def finish_authentication(
    email: str,
    assertion_response: dict[str, Any],
) -> dict[str, Any]:
    """Verify authentication assertion and establish session.

    Full impl:
    1. Retrieve challenge from Redis.
    2. Load user + matching credential by credential ID.
    3. Call webauthn.verify_authentication_response().
    4. Update sign_count in user.passkey_credentials.
    5. Set session cookie (same path as magic link auth in login.py).
    6. Return {"ok": True, "user_id": "..."}.
    """
    logger.info("passkey.finish_authentication called email=%s [STUB]", email)
    return {"error": "not_implemented", "detail": "Passkey authentication not yet configured"}
