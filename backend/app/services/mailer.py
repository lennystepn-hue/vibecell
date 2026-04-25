"""Email delivery via Resend, with dev-mode log fallback."""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_MAGIC_LINK_SUBJECT = "Sign in to Vibecell"

_MAGIC_LINK_HTML = """<!doctype html>
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; background:#070b10; color:#cfd4dc; padding:48px 24px;">
    <div style="max-width:480px;margin:0 auto;">
      <h1 style="color:#fff;font-size:22px;letter-spacing:-0.01em;">◈ Sign in to Vibecell</h1>
      <p style="line-height:1.5;color:#8ba1bd;">Click the button below to sign in. The link expires in 15 minutes and can only be used once.</p>
      <p style="margin:32px 0;">
        <a href="{verify_url}" style="display:inline-block;background:#5cc8a4;color:#070b10;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;">Sign in</a>
      </p>
      <p style="color:#5e7088;font-size:12px;">If the button doesn't work, paste this link: {verify_url}</p>
      <p style="color:#5e7088;font-size:12px;">If you didn't request this, ignore it.</p>
    </div>
  </body>
</html>"""


def _resend_client() -> Any:
    """Return the resend module. Kept as a function so tests can patch."""
    import resend

    resend.api_key = get_settings().resend_api_key
    return resend


async def send_magic_link_email(*, to: str, verify_url: str) -> None:
    settings = get_settings()
    if settings.dev_mode:
        logger.info(
            "DEV MAGIC LINK → to=%s verify_url=%s", to, verify_url
        )
        return

    client = _resend_client()
    payload = {
        "from": "Vibecell <noreply@vibecell.dev>",
        "to": [to],
        "subject": _MAGIC_LINK_SUBJECT,
        "html": _MAGIC_LINK_HTML.format(verify_url=verify_url),
    }
    # Resend SDK 2.x exposes `Emails` as a class with static `send`.
    # Call is sync; we invoke it from async context because it's a single
    # outbound HTTP request per magic-link request (rare) — acceptable.
    client.Emails.send(payload)


_EMAIL_CHANGE_SUBJECT = "Confirm your new email for Vibecell"

_EMAIL_CHANGE_HTML = """<!doctype html>
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; background:#070b10; color:#cfd4dc; padding:48px 24px;">
    <div style="max-width:480px;margin:0 auto;">
      <h1 style="color:#fff;font-size:22px;letter-spacing:-0.01em;">◈ Confirm your new email</h1>
      <p style="line-height:1.5;color:#8ba1bd;">Click the button below to switch your Vibecell account to this email address. The link expires in 24 hours and can only be used once.</p>
      <p style="margin:32px 0;">
        <a href="{confirm_url}" style="display:inline-block;background:#5cc8a4;color:#070b10;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;">Confirm email change</a>
      </p>
      <p style="color:#5e7088;font-size:12px;">If the button doesn't work, paste this link: {confirm_url}</p>
      <p style="color:#5e7088;font-size:12px;">If you didn't request this change, you can safely ignore this email — your account stays on its current address.</p>
    </div>
  </body>
</html>"""


async def send_email_change_email(*, to: str, confirm_url: str) -> None:
    """Mail a one-time confirmation link to the NEW address requested in
    a /me/change-email flow. Dev mode logs instead of sending."""
    settings = get_settings()
    if settings.dev_mode:
        logger.info(
            "DEV EMAIL CHANGE → to=%s confirm_url=%s", to, confirm_url
        )
        return

    client = _resend_client()
    payload = {
        "from": "Vibecell <noreply@vibecell.dev>",
        "to": [to],
        "subject": _EMAIL_CHANGE_SUBJECT,
        "html": _EMAIL_CHANGE_HTML.format(confirm_url=confirm_url),
    }
    client.Emails.send(payload)
