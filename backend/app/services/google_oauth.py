"""Google "Sign in with Google" OAuth 2.0 + OpenID flow.

Authorization Code flow with PKCE (S256). State + verifier live in Redis
keyed by random `state` (TTL 5 min, single-use, deleted on consume so
replay attempts fail). On callback we exchange the code via Google's
token endpoint, fetch /v3/userinfo with the access_token, and hand the
verified email to login_or_bootstrap_user — same path magic-link auth
takes after token verification.

Endpoints registered at app/api/v1/auth_google.py:
  GET /api/v1/auth/google/start    — kick off, redirect to Google consent
  GET /api/v1/auth/google/callback — handle Google's redirect, set session

Configure in /etc/hangar/hangar.env:
  HANGAR_GOOGLE_CLIENT_ID=...apps.googleusercontent.com
  HANGAR_GOOGLE_CLIENT_SECRET=...

In Google Cloud Console (APIs & Services → Credentials → OAuth 2.0):
  Authorized redirect URIs:
    https://vibecell.dev/api/v1/auth/google/callback
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# Google's discovery endpoints (https://accounts.google.com/.well-known/openid-configuration)
_GOOGLE_AUTHZ_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

# State TTL — generous enough for OAuth dance + browser redirects, tight
# enough that abandoned flows don't accumulate in Redis forever.
_STATE_TTL_SECONDS = 300

# Scopes we ask for. openid + email is the minimum to get a verified email
# back; profile lets us greet by name later if we want it (we don't store
# anything beyond email today).
_SCOPES = "openid email profile"


class GoogleOAuthError(Exception):
    """Raised when the Google OAuth dance fails — caller turns into a redirect to /login?err=..."""


def _state_key(state: str) -> str:
    return f"google_oauth:state:{state}"


def is_configured() -> bool:
    s = get_settings()
    return bool(s.google_client_id and s.google_client_secret)


def _redirect_uri() -> str:
    """The exact URI registered in the Google Cloud Console. Must match
    byte-for-byte or Google rejects the exchange."""
    return f"{get_settings().base_url.rstrip('/')}/api/v1/auth/google/callback"


def _b64url_no_pad(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


async def begin(*, next_path: str | None = None) -> str:
    """Generate state + PKCE verifier, store in Redis, return the Google
    consent URL the caller should redirect the browser to.

    `next_path` is preserved in the state record so we can hand the user
    back to the page they were trying to reach after auth (defaults to /p).
    """
    if not is_configured():
        raise GoogleOAuthError("Google login isn't configured on this server")

    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _b64url_no_pad(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    )

    redis = await get_redis()
    payload = {
        "code_verifier": code_verifier,
        "next_path": next_path or "/p",
    }
    await redis.set(
        _state_key(state),
        json.dumps(payload),
        ex=_STATE_TTL_SECONDS,
    )

    params = {
        "client_id": get_settings().google_client_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": _SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        # Force account-chooser when the user has multiple Google accounts.
        # Better UX than silently picking whichever they're signed in to.
        "prompt": "select_account",
        # Prevents Google from including "consent" UI for users who already
        # granted access, but still keeps account-chooser via prompt above.
        "access_type": "online",
        "include_granted_scopes": "true",
    }
    return f"{_GOOGLE_AUTHZ_URL}?{urlencode(params)}"


async def consume(*, state: str, code: str) -> tuple[str, str]:
    """Validate the state Google redirected back with, exchange the code
    for tokens, fetch userinfo, and return (email, next_path) for the
    caller to bootstrap + redirect.

    State is deleted on first read — replay protection.
    """
    if not is_configured():
        raise GoogleOAuthError("Google login isn't configured on this server")
    if not state or not code:
        raise GoogleOAuthError("missing state or code")

    redis = await get_redis()
    raw = await redis.getdel(_state_key(state))
    if raw is None:
        # State expired or already consumed (replay attempt).
        raise GoogleOAuthError("state expired or invalid — try again")
    try:
        payload = json.loads(raw)
        code_verifier: str = payload["code_verifier"]
        next_path: str = payload.get("next_path") or "/p"
    except (json.JSONDecodeError, KeyError) as exc:
        raise GoogleOAuthError("malformed state record") from exc

    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": _redirect_uri(),
                    "code_verifier": code_verifier,
                },
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            logger.warning("google_oauth: token exchange failed (network): %s", exc)
            raise GoogleOAuthError("couldn't reach Google's token endpoint") from exc

        if resp.status_code != 200:
            logger.warning(
                "google_oauth: token exchange %s: %s", resp.status_code, resp.text[:300]
            )
            raise GoogleOAuthError("Google rejected the authorization code")

        token_data: dict[str, Any] = resp.json()
        access_token = token_data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise GoogleOAuthError("no access_token in Google response")

        # Fetch userinfo. id_token would also carry email but parsing it
        # without verifying the signature is unsafe; userinfo is bound to
        # the token we just obtained so trust transfers.
        try:
            ui_resp = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError as exc:
            logger.warning("google_oauth: userinfo failed (network): %s", exc)
            raise GoogleOAuthError("couldn't reach Google's userinfo endpoint") from exc

        if ui_resp.status_code != 200:
            logger.warning(
                "google_oauth: userinfo %s: %s",
                ui_resp.status_code, ui_resp.text[:300],
            )
            raise GoogleOAuthError("Google userinfo call failed")

        ui: dict[str, Any] = ui_resp.json()
        email = ui.get("email")
        email_verified = ui.get("email_verified")
        if not isinstance(email, str) or not email:
            raise GoogleOAuthError("no email in Google userinfo")
        if email_verified is False:
            # Should never happen for typical Google accounts, but if a
            # user managed to wire up an unverified email we don't trust it.
            raise GoogleOAuthError("Google account email isn't verified")

    return email.strip().lower(), next_path
