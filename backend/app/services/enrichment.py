"""AI-powered project enrichment using Anthropic Claude.

Called during GitHub import to generate rich project metadata from README +
manifest files. Graceful fallback if API key missing or API fails.

Returns a best-guess, structured picture of the project:
- pitch, tags, stack, infra (what IS this?)
- environments (where does it run?)
- commands (how do I run/deploy it?)
- extra_links (docs, API, admin, metrics beyond github+homepage)
- emoji (one emoji that captures the domain)

The consumer (enrichment_apply.apply_enrichment_to_project) merges this into
the project's DB rows idempotently — never clobbering existing non-null fields.
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
    emoji: str | None = None
    tags: list[str] = field(default_factory=list)
    stack: list[dict[str, str]] = field(default_factory=list)  # [{slug, name, kind, role}]
    infra: dict[str, str] = field(default_factory=dict)  # {framework, db, cdn, ...}
    environments: list[dict[str, str]] = field(
        default_factory=list,
    )  # [{kind: local|staging|prod, url, env_template_path}]
    commands: list[dict[str, str]] = field(
        default_factory=list,
    )  # [{label, command, run_in: terminal|browser, confirm_required: bool}]
    extra_links: list[dict[str, str]] = field(
        default_factory=list,
    )  # [{kind: docs|api|metrics|admin|other, label, url}]
    notes: str | None = None  # freeform for debugging


# Files we pull from the repo to give the LLM a rich picture. Kept tight for
# token budget — the LLM cares about intent (README), stack signals (manifests),
# runtime shape (Dockerfile/compose), and run-shell commands (Makefile/scripts).
_REPO_FILES = [
    "README.md", "readme.md", "README",
    "package.json", "pnpm-workspace.yaml",
    "pyproject.toml", "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "composer.json",
    "Gemfile",
    "docker-compose.yml", "docker-compose.yaml", "compose.yml",
    "Dockerfile",
    "Makefile", "justfile", ".justfile",
    ".env.example", "env.example",
    "vite.config.ts", "vite.config.js",
    "next.config.js", "next.config.mjs",
    "docs/deploy.md", "DEPLOY.md",
]


async def fetch_repo_context(token: str, owner: str, name: str, default_branch: str) -> dict[str, str]:
    """Fetch README + manifests + runtime/build files from a GitHub repo.

    Returns {file_path: content_truncated_to_8kb}. Ignores missing files.
    """
    out: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=15) as client:
        for path in _REPO_FILES:
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
    homepage_url: str | None = None,
) -> EnrichmentResult:
    """Run the LLM to generate enrichment metadata.

    Graceful fallback — returns empty EnrichmentResult if API unavailable.
    """
    s = get_settings()
    if not s.anthropic_api_key:
        return EnrichmentResult(notes="ANTHROPIC_API_KEY not set — enrichment skipped")

    # Compose the prompt. More files = richer result, but we cap total length.
    file_summaries = "\n\n".join(
        f"=== {p} ({len(c)} chars) ===\n{c[:3000]}"
        for p, c in fetched_files.items()
    )[:20000]

    user_prompt = f"""Analyze this GitHub repository and return enriched metadata as strict JSON.

You are populating a project-dashboard card for a developer. They just imported
this repo and want a "fully populated" overview without typing anything. Pull
EVERYTHING you can reasonably infer from the files below — don't be shy.

Repo: {name}
Description: {description or '(none)'}
Primary language: {language or '(unknown)'}
Existing topics: {topics}
Homepage: {homepage_url or '(none)'}

Files:
{file_summaries or '(no files fetched)'}

Return ONLY JSON matching this shape (no markdown, no prose, no code fences):
{{
  "pitch": "One sentence, under 140 chars. What is this? Who is it for?",
  "emoji": "🚀",
  "tags": ["up to 8 lowercase kebab-case tags"],
  "stack": [{{"slug": "vue-3", "name": "Vue 3", "kind": "framework", "role": "frontend"}}],
  "infra": {{"framework": "FastAPI", "db": "Postgres", "cdn": null}},
  "environments": [
    {{"kind": "local", "url": "http://localhost:3000", "env_template_path": ".env.example"}},
    {{"kind": "prod", "url": "https://example.com"}}
  ],
  "commands": [
    {{"label": "dev", "command": "pnpm dev", "run_in": "terminal"}},
    {{"label": "build", "command": "pnpm build", "run_in": "terminal"}},
    {{"label": "test", "command": "pnpm test", "run_in": "terminal"}}
  ],
  "extra_links": [
    {{"kind": "docs", "label": "Docs", "url": "https://example.com/docs"}}
  ]
}}

Rules:
- pitch: punchy, specific, matches what the repo actually IS. If description is meaningful, expand/sharpen it. Don't parrot the repo name.
- emoji: ONE emoji that captures the domain (e.g. 🤖 for AI tool, 💳 for payments, 📚 for docs, 🎁 for gifts, 🔍 for search, 🔐 for security, 🎨 for design tool, 📊 for analytics, 🎮 for games, 🗺️ for maps). NO generic emojis like 📦 — they fall back to 📦 on the client anyway.
- tags: keep existing topics + add domain-specific ones (e.g. "oauth", "mcp", "saas", "ai", "gift-guide"). 8 max, lowercase kebab-case.
- stack: primary language + frameworks + notable deps from package.json/pyproject/Cargo/go.mod. kind in [language, framework, library, db, tool, service]. role in [frontend, backend, fullstack, cli, devops, testing, language]. Up to 10 items.
- infra: keys [framework, db, cdn, object_storage, dns_provider, server_alias]; value null if not present in the files. Don't guess.
- environments: infer from README "dev", "local", "production" sections + docker-compose ports + homepage URL. kind must be one of [local, staging, prod]. If README shows `http://localhost:3000` → local env. If homepage is set → prod env with that URL. env_template_path optional; set to ".env.example" if that file exists.
- commands: pull from package.json "scripts" (pnpm dev, npm start, etc.), Makefile targets, justfile recipes, or Cargo aliases. run_in always "terminal". Omit `confirm_required`; defaults to false. Up to 8 commands. Skip trivial ones (lint, format); keep run/build/test/deploy.
- extra_links: pull from README badges + "Docs:" / "API:" / "Admin:" sections. kind in [docs, api, metrics, admin, other]. Omit github + homepage (already handled). Up to 4.
- If a field has no reasonable value, return an empty array/object/null — never invent.
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
                    "max_tokens": 2048,  # bumped — we now return more structure
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
            emoji=parsed.get("emoji"),
            tags=parsed.get("tags") or [],
            stack=parsed.get("stack") or [],
            infra={k: v for k, v in (parsed.get("infra") or {}).items() if v},
            environments=[
                e for e in (parsed.get("environments") or [])
                if isinstance(e, dict) and e.get("kind") in {"local", "staging", "prod"} and e.get("url")
            ],
            commands=[
                c for c in (parsed.get("commands") or [])
                if isinstance(c, dict) and c.get("label") and c.get("command")
            ],
            extra_links=[
                lnk for lnk in (parsed.get("extra_links") or [])
                if isinstance(lnk, dict) and lnk.get("url") and lnk.get("label")
            ],
        )
    except Exception as e:
        log.warning("enrichment: failed %s", e)
        return EnrichmentResult(notes=f"exception_{type(e).__name__}")
