"""Test helpers for mocking GitHub API calls."""
from typing import Any
from unittest.mock import AsyncMock

import pytest


def patch_github(monkeypatch: pytest.MonkeyPatch, responses: dict[str, Any]) -> None:
    """Stub the `app.services.github` module's network-touching functions.

    `responses` is a dict with keys: "exchange_code", "me", "list_user_repos",
    "get_repo". Each value is the return value (or an Exception to raise).
    """
    import app.services.github as gh

    for name in ("exchange_code", "me", "list_user_repos", "get_repo"):
        if name in responses:
            value = responses[name]
            mock = AsyncMock(return_value=value if not isinstance(value, Exception) else None)
            if isinstance(value, Exception):
                mock.side_effect = value
            monkeypatch.setattr(gh, name, mock)
