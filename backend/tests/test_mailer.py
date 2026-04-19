from typing import Any

import pytest

from app.services.mailer import send_magic_link_email


async def test_dev_mode_logs_instead_of_sending(monkeypatch: pytest.MonkeyPatch) -> None:
    """In dev mode, the mailer must NOT call Resend. Verify by monkeypatching
    the Resend factory — if it were invoked, the test would see the sentinel."""
    monkeypatch.setenv("HANGAR_DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.setenv("HANGAR_DEV_MODE", "1")
    from app.core.config import get_settings
    get_settings.cache_clear()

    resend_called = False

    class _TripwireResend:
        class emails:  # noqa: N801
            @staticmethod
            def send(payload: dict[str, Any]) -> dict[str, str]:
                nonlocal resend_called
                resend_called = True
                return {"id": "should-not-be-reached"}

    import app.services.mailer as mailer
    monkeypatch.setattr(mailer, "_resend_client", lambda: _TripwireResend)

    await send_magic_link_email(
        to="u@example.com",
        verify_url="http://localhost:3000/auth/verify?token=abc",
    )

    assert resend_called is False, "dev mode should short-circuit before hitting Resend"


async def test_production_mode_calls_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that when dev_mode is False, we call the Resend client."""
    monkeypatch.setenv("HANGAR_DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.setenv("HANGAR_DEV_MODE", "0")
    monkeypatch.setenv("HANGAR_RESEND_API_KEY", "re_fake")
    from app.core.config import get_settings
    get_settings.cache_clear()

    sent_payloads: list[dict[str, Any]] = []

    class _FakeEmails:
        @staticmethod
        def send(payload: dict[str, Any]) -> dict[str, str]:
            sent_payloads.append(payload)
            return {"id": "fake-message-id"}

    class _FakeResend:
        emails = _FakeEmails()

    import app.services.mailer as mailer
    monkeypatch.setattr(mailer, "_resend_client", lambda: _FakeResend)

    await send_magic_link_email(
        to="u@example.com",
        verify_url="http://localhost:3000/auth/verify?token=abc",
    )

    assert len(sent_payloads) == 1
    payload = sent_payloads[0]
    assert payload["to"] == ["u@example.com"]
    assert "Sign in to Vibecell" in payload["subject"]
    assert "abc" in payload["html"]
