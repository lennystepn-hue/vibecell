"""TOTP (RFC 6238) second-factor for admin actions.

The user provisions once via /api/v1/2fa/setup (we generate a 160-bit
secret + return an otpauth:// URI rendered as a base64 QR png), confirms
their authenticator with /api/v1/2fa/verify (must input a valid code,
which marks `totp_enabled_at` and persists the encrypted secret), then
every admin write action requires a fresh code via the require_admin_2fa
dependency.

Secrets are AES-256-GCM encrypted at rest using the same master key
that wraps the workspace DEKs (see app.core.crypto). Verifying a code
decrypts in-memory, never logs the secret, and uses a 1-step time
window (current ± 30s) to tolerate clock skew without widening the
acceptance window enough to make brute-force feasible.
"""
from __future__ import annotations

import base64
import io
import time
from typing import TYPE_CHECKING

import pyotp
import qrcode

from app.core.config import get_settings
from app.core.crypto import decrypt_with_master, encrypt_with_master

if TYPE_CHECKING:
    from app.models import User

# 30-second TOTP step (RFC 6238 default + every authenticator app default).
_STEP_SECONDS = 30
# How many ±steps we accept. 1 = current code OR previous OR next (so
# user has up to ~60s between typing the code and us validating it,
# tolerating phone clock drift). Anything above 2 weakens the gate.
_VALID_WINDOW = 1

_ISSUER = "Vibecell"


def generate_secret() -> str:
    """160-bit base32 secret — pyotp default. Strong enough for TOTP
    forever; do not shorten."""
    return pyotp.random_base32()


def encrypt_secret(secret: str) -> str:
    """AES-256-GCM-encrypt the base32 secret with the platform master key.
    Returns base64 string. Stored in users.totp_secret_enc (Text column)."""
    return encrypt_with_master(secret, master_key_b64=get_settings().master_key)


def decrypt_secret(blob: str) -> str:
    return decrypt_with_master(blob, master_key_b64=get_settings().master_key)


def otpauth_uri(*, secret: str, account_email: str) -> str:
    """RFC 6238 otpauth:// URI. Authenticator apps (Google Authenticator,
    1Password, Authy, Bitwarden, …) all parse this same format from a
    QR scan."""
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=account_email, issuer_name=_ISSUER,
    )


def qr_data_uri(*, otpauth: str) -> str:
    """Render the otpauth URI to a PNG data-URI for inline <img src=...>.

    PNG (vs SVG) so we don't have to worry about the user's browser
    rejecting an svg with embedded data, and the size is fine — typical
    QR for an otpauth URI is under 2KB.
    """
    img = qrcode.make(otpauth, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def verify_code(*, secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code against the secret with a ±1-step window.

    Constant-time comparison via pyotp internals; no early-out on
    mismatch so we're not leaking timing info. Strips whitespace from
    user input but otherwise validates exactly 6 digits.
    """
    code = (code or "").replace(" ", "").strip()
    if not code.isdigit() or len(code) != 6:
        return False
    totp = pyotp.TOTP(secret, interval=_STEP_SECONDS)
    # Use for_time + valid_window for explicit control over the window.
    return totp.verify(code, for_time=int(time.time()), valid_window=_VALID_WINDOW)


def is_enabled(user: User) -> bool:
    """User has TOTP enabled iff a secret exists AND we've stamped a
    confirmation timestamp (so a half-finished setup doesn't count)."""
    return user.totp_secret_enc is not None and user.totp_enabled_at is not None
