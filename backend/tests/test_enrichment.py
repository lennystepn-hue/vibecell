"""Tests for the AI enrichment service (Spec 3.6)."""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure required Settings fields are present for unit tests that don't spin up a DB.
os.environ.setdefault("HANGAR_DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")

from app.services.enrichment import enrich_from_repo


async def test_enrich_graceful_fallback_when_no_api_key(monkeypatch):
    """Without API key, return empty result instead of raising."""
    monkeypatch.setenv("HANGAR_ANTHROPIC_API_KEY", "")
    from app.core.config import get_settings
    get_settings.cache_clear()

    result = await enrich_from_repo(
        name="test",
        description="x",
        language="Python",
        topics=[],
        fetched_files={},
    )
    assert result.pitch is None
    assert result.tags == []
    assert "skipped" in (result.notes or "")


async def test_enrich_parses_valid_response(monkeypatch):
    """Happy path: LLM returns valid JSON, we parse into EnrichmentResult."""
    monkeypatch.setenv("HANGAR_ANTHROPIC_API_KEY", "sk-ant-test")
    from app.core.config import get_settings
    get_settings.cache_clear()

    fake_payload = {
        "pitch": "A blazing fast REST API framework for Python devs.",
        "tags": ["python", "rest-api", "fastapi", "backend"],
        "stack": [
            {"slug": "python", "name": "Python", "kind": "language", "role": "language"},
            {"slug": "fastapi", "name": "FastAPI", "kind": "framework", "role": "backend"},
        ],
        "infra": {"framework": "FastAPI", "db": "Postgres", "cdn": None},
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": [{"text": json.dumps(fake_payload)}],
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.enrichment.httpx.AsyncClient", return_value=mock_client):
        result = await enrich_from_repo(
            name="my-api",
            description="A REST API",
            language="Python",
            topics=["python", "rest-api"],
            fetched_files={"README.md": "# My API\nFast and furious."},
        )

    assert result.pitch == "A blazing fast REST API framework for Python devs."
    assert "python" in result.tags
    assert "fastapi" in result.tags
    assert any(s["slug"] == "fastapi" for s in result.stack)
    # infra: cdn is null so should be filtered out
    assert result.infra.get("framework") == "FastAPI"
    assert result.infra.get("db") == "Postgres"
    assert "cdn" not in result.infra


async def test_enrich_handles_code_fenced_response(monkeypatch):
    """Model returns JSON wrapped in code fences — should still parse correctly."""
    monkeypatch.setenv("HANGAR_ANTHROPIC_API_KEY", "sk-ant-test")
    from app.core.config import get_settings
    get_settings.cache_clear()

    fenced_text = '```json\n{"pitch": "Hello world", "tags": [], "stack": [], "infra": {}}\n```'

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": [{"text": fenced_text}],
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.enrichment.httpx.AsyncClient", return_value=mock_client):
        result = await enrich_from_repo(
            name="hello", description=None, language=None, topics=[], fetched_files={},
        )

    assert result.pitch == "Hello world"


async def test_enrich_returns_empty_on_api_error(monkeypatch):
    """4xx/5xx from Anthropic → graceful empty result, no exception raised."""
    monkeypatch.setenv("HANGAR_ANTHROPIC_API_KEY", "sk-ant-bad")
    from app.core.config import get_settings
    get_settings.cache_clear()

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.enrichment.httpx.AsyncClient", return_value=mock_client):
        result = await enrich_from_repo(
            name="x", description=None, language=None, topics=[], fetched_files={},
        )

    assert result.pitch is None
    assert "api_error_401" in (result.notes or "")


async def test_enrich_returns_empty_on_network_exception(monkeypatch):
    """Network failure → graceful empty result, no exception raised."""
    monkeypatch.setenv("HANGAR_ANTHROPIC_API_KEY", "sk-ant-ok")
    from app.core.config import get_settings
    get_settings.cache_clear()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=Exception("connection refused"))

    with patch("app.services.enrichment.httpx.AsyncClient", return_value=mock_client):
        result = await enrich_from_repo(
            name="x", description=None, language=None, topics=[], fetched_files={},
        )

    assert result.pitch is None
    assert result.notes is not None
    assert "exception_" in result.notes
