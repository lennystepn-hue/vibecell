# Hangar

The operating system for vibecoders.

- Full spec: [HANGAR.md](HANGAR.md)
- Spec 1 design: [docs/superpowers/specs/2026-04-18-spec-1-foundation-dashboard-design.md](docs/superpowers/specs/2026-04-18-spec-1-foundation-dashboard-design.md)
- Spec 1 plan: [docs/superpowers/plans/spec-1/README.md](docs/superpowers/plans/spec-1/README.md)

## Dev quickstart

```bash
docker compose -f ops/docker-compose.dev.yml up -d
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000
cd frontend && pnpm install && pnpm dev
```

Open http://localhost:3000 — proxies `/api` to backend.
