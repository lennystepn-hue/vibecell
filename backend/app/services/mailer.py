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


# ---------------------------------------------------------------------------
# Spec-6 Sprint B5 — billing transactional emails
# ---------------------------------------------------------------------------

_TRIAL_ENDING_SUBJECT = "Your Vibecell trial ends in 2 days"

_TRIAL_ENDING_HTML = """<!doctype html>
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; background:#070b10; color:#cfd4dc; padding:48px 24px;">
    <div style="max-width:480px;margin:0 auto;">
      <h1 style="color:#fff;font-size:22px;letter-spacing:-0.01em;">⏳ Trial ending soon</h1>
      <p style="line-height:1.5;color:#8ba1bd;">Your free trial of Vibecell Pro ends in 2 days. Add a payment method to keep using projects, AI enrichment, and the MCP integration without interruption.</p>
      <p style="margin:32px 0;">
        <a href="{billing_url}" style="display:inline-block;background:#5cc8a4;color:#070b10;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;">Add payment method — €8.99/mo</a>
      </p>
      <p style="color:#5e7088;font-size:12px;">Trial users keep all features through the trial window. After it ends, your subscription pauses until a payment method is on file.</p>
    </div>
  </body>
</html>"""

_PAYMENT_FAILED_SUBJECT = "Vibecell payment failed — please update your card"

_PAYMENT_FAILED_HTML = """<!doctype html>
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; background:#070b10; color:#cfd4dc; padding:48px 24px;">
    <div style="max-width:480px;margin:0 auto;">
      <h1 style="color:#fff;font-size:22px;letter-spacing:-0.01em;">⚠️ Payment failed</h1>
      <p style="line-height:1.5;color:#8ba1bd;">We couldn't process your latest €8.99 charge. Stripe will retry automatically over the next few days, but updating your card now avoids any interruption.</p>
      <p style="margin:32px 0;">
        <a href="{billing_url}" style="display:inline-block;background:#ff7e6c;color:#070b10;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;">Update payment method</a>
      </p>
      <p style="color:#5e7088;font-size:12px;">If your subscription stays past_due for more than 7 days, your account becomes read-only — projects + sessions are preserved.</p>
    </div>
  </body>
</html>"""


async def send_trial_ending_email(*, to: str, billing_url: str) -> None:
    """Sent at T-3 days AND T-1 day before trial_ends_at (multi-stage
    state machine in trial_lifecycle.py keeps this idempotent)."""
    settings = get_settings()
    if settings.dev_mode:
        logger.info("DEV TRIAL ENDING → to=%s billing_url=%s", to, billing_url)
        return
    client = _resend_client()
    payload = {
        "from": "Vibecell <noreply@vibecell.dev>",
        "to": [to],
        "subject": _TRIAL_ENDING_SUBJECT,
        "html": _TRIAL_ENDING_HTML.format(billing_url=billing_url),
    }
    client.Emails.send(payload)


_TRIAL_ENDED_SUBJECT = "Your Vibecell trial has ended"
_TRIAL_ENDED_HTML = """\
<html>
  <body style="font-family:ui-sans-serif,system-ui,sans-serif;background:#070b10;color:#cfd4dc;padding:32px;">
    <div style="max-width:520px;margin:0 auto;background:#0d1218;border:1px solid rgba(138,180,255,0.08);border-radius:12px;padding:32px;">
      <p style="font-family:ui-monospace,monospace;color:#5cc8a4;font-size:11px;letter-spacing:.12em;text-transform:uppercase;margin:0 0 12px;">// trial expired</p>
      <h1 style="color:#fff;font-size:22px;margin:0 0 16px;">Your Vibecell trial has ended.</h1>
      <p style="margin:0 0 12px;line-height:1.55;">
        Your account is now read-only — your projects, sessions, decisions and
        ships are all preserved. To resume writing (logging sessions, ticking
        todos, shipping) drop a card below.
      </p>
      <p style="margin:24px 0;">
        <a href="{billing_url}" style="display:inline-block;background:#5cc8a4;color:#070b10;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;">Activate paid plan</a>
      </p>
      <p style="color:#5e7088;font-size:12px;line-height:1.5;">
        €8.99/mo monthly · €99.99/yr annual · LAUNCH69 (€69.99/yr) for the
        first 100 customers. Read-only access stays forever — your data isn't
        going anywhere.
      </p>
    </div>
  </body>
</html>"""


async def send_trial_ended_email(*, to: str, billing_url: str) -> None:
    """Sent at T-0 when status flips trialing → past_due. Final
    notification — user's account just became read-only."""
    settings = get_settings()
    if settings.dev_mode:
        logger.info("DEV TRIAL ENDED → to=%s billing_url=%s", to, billing_url)
        return
    client = _resend_client()
    payload = {
        "from": "Vibecell <noreply@vibecell.dev>",
        "to": [to],
        "subject": _TRIAL_ENDED_SUBJECT,
        "html": _TRIAL_ENDED_HTML.format(billing_url=billing_url),
    }
    client.Emails.send(payload)


async def send_payment_failed_email(*, to: str, billing_url: str) -> None:
    """Triggered by the invoice.payment_failed webhook handler."""
    settings = get_settings()
    if settings.dev_mode:
        logger.info("DEV PAYMENT FAILED → to=%s billing_url=%s", to, billing_url)
        return
    client = _resend_client()
    payload = {
        "from": "Vibecell <noreply@vibecell.dev>",
        "to": [to],
        "subject": _PAYMENT_FAILED_SUBJECT,
        "html": _PAYMENT_FAILED_HTML.format(billing_url=billing_url),
    }
    client.Emails.send(payload)
