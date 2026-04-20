# Spec 3.6 — AI-Powered Project Enrichment on GitHub Import

**Date:** 2026-04-20
**Status:** Implemented

## Goal

When a user imports a GitHub repository into Hangar, automatically generate richer project metadata using an LLM — a punchy one-sentence pitch, domain-specific tags, a full stack list, and infrastructure hints — rather than relying solely on the repo's description and topic list.

## Approach

1. **File fetching (`fetch_repo_context`)** — After the GitHub repo metadata is fetched, a second async pass downloads up to 11 well-known files (README.md, package.json, pyproject.toml, Cargo.toml, requirements.txt, go.mod, composer.json, docker-compose.yml, etc.) from the repo's default branch via the GitHub raw content API. Each file is truncated to 8 KB.

2. **LLM call (`enrich_from_repo`)** — A single prompt is sent to `claude-haiku-4-5-20251001` (cheap, fast) containing the repo name, description, primary language, topics, and a digest of the fetched files. The model returns strict JSON with four keys: `pitch`, `tags`, `stack`, `infra`.

3. **Apply results** — Back in `bulk_import`:
   - `pitch` overwrites the project pitch if the existing value is blank or under 20 characters.
   - `tags` are created/linked against the workspace (deduped against existing topic-derived tags).
   - `stack` items are created/linked to the project (deduped by slug).
   - `infra` is written as a `ProjectInfra` row if none exists yet.

## Fallback Behavior

Every failure mode is graceful — the import itself is never blocked:
- `HANGAR_ANTHROPIC_API_KEY` not set → skip enrichment silently (logged at DEBUG).
- API returns 4xx/5xx → log a warning, return empty `EnrichmentResult`.
- Network failure / JSON parse error → log a warning, return empty `EnrichmentResult`.
- Any unexpected exception in the enrichment block → caught by the inner `try/except`, logged as a warning, import continues.

## Cost Implications

Each import call fires one Anthropic API request using `claude-haiku-4-5-20251001`. At April 2026 pricing (~$0.80/M input, $4/M output), a typical import with a medium README costs under $0.001 per repo. Bulk importing 100 repos in a single request costs ~$0.05–0.10 total.

## Non-Goals

- No streaming / progressive enrichment in the API response (fire-and-forget within the import transaction).
- No re-enrichment of already-imported projects (separate future spec).
- No user-visible AI attribution in the UI for this phase.
- No model selection UI — model is hardcoded to Haiku for cost reasons; upgrading is a config change.
