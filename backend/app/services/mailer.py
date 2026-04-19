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
    # Resend SDK is sync; we call it synchronously from async context.
    # Acceptable for an outbound call that only runs on magic-link request.
    client.emails.send(payload)
