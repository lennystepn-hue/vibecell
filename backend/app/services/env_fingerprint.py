"""Environment fingerprint helpers.

A 'fingerprint' is a SHA-256 hash of a manifest file's content (package.json,
pyproject.toml, Dockerfile, compose.yml, README.md, etc.). We store these
keyed by path on `project_context.env_fingerprint` so Claude can detect
runtime-environment drift between sessions and refresh enrichment.

Shape on disk:
    {
      "files": { "package.json": "<sha256>", "pyproject.toml": "<sha256>" },
      "scanned_at": "2026-04-24T10:11:12+00:00",
      "local_path": "C:/Users/ender/.../Hangar"
    }
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

# Max content size accepted per manifest (protects the Anthropic prompt +
# keeps DB payloads sane). Matches fetch_repo_context in enrichment.py.
MAX_MANIFEST_BYTES = 8000

# Manifest filenames we care about. The server accepts whatever the client
# sends, but this is the curated list SKILL.md tells Claude to read locally.
TRACKED_MANIFESTS: list[str] = [
    "README.md", "readme.md", "README",
    "package.json",
    "pyproject.toml", "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "composer.json",
    "Gemfile",
    "docker-compose.yml", "docker-compose.yaml", "compose.yml",
    "Dockerfile",
    ".env.example", "env.example",
]


def hash_file_content(content: str) -> str:
    """SHA-256 of the (utf-8-encoded) manifest content. Returns 64-char hex."""
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


def build_fingerprint(
    manifests: dict[str, str],
    *,
    local_path: str | None,
) -> dict[str, Any]:
    """Compute a fingerprint dict from current manifests."""
    files: dict[str, str] = {}
    for path, content in manifests.items():
        if not path or content is None:
            continue
        # Normalize path separators so Windows backslash doesn't collide with forward slash.
        key = path.replace("\\", "/")
        files[key] = hash_file_content(content[:MAX_MANIFEST_BYTES])
    return {
        "files": files,
        "scanned_at": datetime.now(UTC).isoformat(),
        "local_path": local_path,
    }


@dataclass
class DriftResult:
    """Summary of drift between a stored and fresh fingerprint."""

    never_scanned: bool = False
    drifted: bool = False
    changed_files: list[str] = None  # paths present in both, hash differs
    new_files: list[str] = None      # paths present in fresh only
    removed_files: list[str] = None  # paths present in stored only
    last_scanned: str | None = None

    def __post_init__(self) -> None:
        if self.changed_files is None:
            self.changed_files = []
        if self.new_files is None:
            self.new_files = []
        if self.removed_files is None:
            self.removed_files = []


def compute_drift(
    stored: dict[str, Any] | None,
    fresh_manifests: dict[str, str],
) -> DriftResult:
    """Compare a stored fingerprint against fresh manifest contents."""
    if not stored or not isinstance(stored, dict) or not stored.get("files"):
        return DriftResult(never_scanned=True, drifted=False)

    stored_files: dict[str, str] = stored.get("files") or {}
    fresh_files: dict[str, str] = {
        path.replace("\\", "/"): hash_file_content(content[:MAX_MANIFEST_BYTES])
        for path, content in (fresh_manifests or {}).items()
        if path and content is not None
    }

    result = DriftResult(last_scanned=stored.get("scanned_at"))

    stored_set = set(stored_files.keys())
    fresh_set = set(fresh_files.keys())

    result.new_files = sorted(fresh_set - stored_set)
    result.removed_files = sorted(stored_set - fresh_set)
    result.changed_files = sorted(
        path for path in (stored_set & fresh_set)
        if stored_files[path] != fresh_files[path]
    )
    result.drifted = bool(result.changed_files or result.new_files or result.removed_files)
    return result
