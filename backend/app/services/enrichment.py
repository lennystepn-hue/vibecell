"""AI-powered project enrichment using Anthropic Claude.

Called during GitHub import to generate rich project metadata from README +
manifest files. Graceful fallback if API key missing or API fails.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"  # cheap + fast for summarization


@dataclass
class EnrichmentResult:
    pitch: str | None = None
    tags: list[str] = field(default_factory=list)
    stack: list[dict[str, str]] = field(default_factory=list)  # [{slug, name, kind, role}]
    infra: dict[str, str] = field(default_factory=dict)  # {framework, db, cdn, ...}
    notes: str | None = None  # freeform for debugging


async def fetch_repo_context(token: str, owner: str, name: str, default_branch: str) -> dict[str, str]:
    """Fetch README + manifest files from a GitHub repo.

    Returns {file_path: content_truncated_to_8kb}. Ignores missing files.
    """
    files_to_try = [
        "README.md", "readme.md", "README",
        "package.json", "pyproject.toml", "Cargo.toml",
        "requirements.txt", "go.mod", "composer.json",
        "docker-compose.yml", "docker-compose.yaml",
    ]
    out: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=15) as client:
        for path in files_to_try:
            url = f"https://api.github.com/repos/{owner}/{name}/contents/{path}?ref={default_branch}"
            try:
                r = await client.get(url, headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3.raw",
                    "X-GitHub-Api-Version": "2022-11-28",
                })
                if r.status_code == 200:
                    out[path] = r.text[:8000]
            except Exception:
                continue
    return out


async def enrich_from_repo(
    *,
    name: str,
    description: str | None,
    language: str | None,
    topics: list[str],
    fetched_files: dict[str, str],
) -> EnrichmentResult:
    """Run the LLM to generate enrichment metadata.

    Graceful fallback — returns empty EnrichmentResult if API unavailable.
    """
    s = get_settings()
    if not s.anthropic_api_key:
        return EnrichmentResult(notes="ANTHROPIC_API_KEY not set — enrichment skipped")

    # Compose the prompt
    file_summaries = "\n\n".join(
        f"=== {p} ({len(c)} chars) ===\n{c[:3000]}"
        for p, c in fetched_files.items()
    )[:15000]

    user_prompt = f"""Analyze this GitHub repository and return enriched metadata as strict JSON.

Repo: {name}
Description: {description or '(none)'}
Primary language: {language or '(unknown)'}
Existing topics: {topics}

Files:
{file_summaries or '(no files fetched)'}

Return ONLY JSON matching this shape (no markdown, no prose, no code fences):
{{
  "pitch": "One sentence, under 140 chars. What is this? Who is it for?",
  "tags": ["up to 8 lowercase kebab-case tags"],
  "stack": [{{"slug": "vue-3", "name": "Vue 3", "kind": "framework", "role": "frontend"}}],
  "infra": {{"framework": "FastAPI", "db": "Postgres", "cdn": null}}
}}

Rules:
- pitch: punchy, specific, matches what the repo actually IS
- tags: keep existing topics + add domain-specific ones (e.g. "oauth", "mcp", "saas")
- stack: primary language + frameworks + notable deps. kind in [language, framework, library, db, tool, service]. role in [frontend, backend, fullstack, cli, devops, testing, language]
- infra: keys are [framework, db, cdn, object_storage, dns_provider, server_alias]; value null if unknown
"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _ANTHROPIC_URL,
                headers={
                    "x-api-key": s.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": _MODEL,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )
        if resp.status_code >= 400:
            log.warning("enrichment: Anthropic API %d: %s", resp.status_code, resp.text[:200])
            return EnrichmentResult(notes=f"api_error_{resp.status_code}")

        data = resp.json()
        text = data["content"][0]["text"].strip()
        # Strip code fences if model included them despite the instruction
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.rsplit("```", 1)[0].strip()
            if text.startswith("json\n"):
                text = text[5:]

        parsed = json.loads(text)
        return EnrichmentResult(
            pitch=parsed.get("pitch"),
            tags=parsed.get("tags") or [],
            stack=parsed.get("stack") or [],
            infra={k: v for k, v in (parsed.get("infra") or {}).items() if v},
        )
    except Exception as e:
        log.warning("enrichment: failed %s", e)
        return EnrichmentResult(notes=f"exception_{type(e).__name__}")
