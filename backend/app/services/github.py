"""GitHub API client (OAuth exchange + repo operations)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import HangarError

_GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_API = "https://api.github.com"


def authorize_url(*, state: str, redirect_uri: str) -> str:
    s = get_settings()
    from urllib.parse import urlencode

    params = {
        "client_id": s.github_client_id,
        "redirect_uri": redirect_uri,
        "scope": "read:user repo",
        "state": state,
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


async def exchange_code(*, code: str, redirect_uri: str) -> str:
    """Return access_token from GitHub. Raises HangarError on failure."""
    s = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            _GITHUB_OAUTH_TOKEN_URL,
            data={
                "client_id": s.github_client_id,
                "client_secret": s.github_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
    if resp.status_code >= 400:
        raise HangarError(
            title="GitHub OAuth failed",
            status=502,
            type_="/errors/github-oauth",
            detail=f"token exchange returned {resp.status_code}",
        )
    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise HangarError(
            title="GitHub OAuth failed",
            status=502,
            type_="/errors/github-oauth",
            detail=payload.get("error_description") or "no access_token in response",
        )
    return str(token)


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def me(token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{_GITHUB_API}/user", headers=_auth_headers(token))
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    return data


async def list_user_repos(
    token: str, *, page: int = 1, per_page: int = 30, q: str | None = None,
) -> list[dict[str, Any]]:
    """List repos the authenticated user can access. `q` filters client-side by name."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_GITHUB_API}/user/repos",
            headers=_auth_headers(token),
            params={"page": page, "per_page": per_page, "sort": "updated"},
        )
    resp.raise_for_status()
    repos: list[dict[str, Any]] = resp.json()
    if q:
        ql = q.lower()
        repos = [r for r in repos if ql in (r.get("name") or "").lower()]
    return repos


async def get_repo(token: str, owner: str, name: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_GITHUB_API}/repos/{owner}/{name}",
            headers=_auth_headers(token),
        )
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    return data


def normalize_repo(gh: dict[str, Any]) -> dict[str, Any]:
    """Trim GitHub response to the fields we expose."""
    owner = gh.get("owner", {}).get("login", "")
    name = gh.get("name", "")
    full_name = gh.get("full_name") or f"{owner}/{name}"
    pushed_at_str = gh.get("pushed_at")
    pushed_at = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00")) if pushed_at_str else None
    return {
        "owner": owner,
        "name": name,
        "full_name": full_name,
        "description": gh.get("description"),
        "private": bool(gh.get("private", False)),
        "default_branch": gh.get("default_branch") or "main",
        "language": gh.get("language"),
        "license_spdx": (gh.get("license") or {}).get("spdx_id") if gh.get("license") else None,
        "homepage": gh.get("homepage"),
        "clone_url": gh.get("clone_url") or gh.get("ssh_url") or "",
        "pushed_at": pushed_at,
    }
