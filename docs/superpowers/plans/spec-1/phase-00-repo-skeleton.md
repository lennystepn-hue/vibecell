# Phase 0 — Repo Skeleton & Tooling

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Create the monorepo layout, development Docker Compose, minimal FastAPI and Vue apps that respond on their ports, and a lint/typecheck CI baseline.

**Architecture:** `backend/` is a uv-managed Python package (pyproject). `frontend/` is a pnpm-managed Vite+Vue app. `ops/docker-compose.dev.yml` runs Postgres 16 and Redis 7 only — backend/frontend run on host in dev for fast reload. Caddy + backend/frontend containers come in Phase 17.

**Tech Stack:** Python 3.12 + uv, Node 20 + pnpm 9, Docker 24, GitHub Actions.

---

## File structure produced by this phase

```
hangar/
├── .github/workflows/ci.yml
├── .editorconfig
├── .gitignore                 (already exists, extend)
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py            minimal FastAPI app + /healthz
│   ├── tests/
│   │   └── test_healthz.py
│   ├── .env.example
│   ├── pyproject.toml
│   └── README.md
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── env.d.ts
│   ├── index.html
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── README.md
├── ops/
│   ├── docker-compose.dev.yml
│   └── postgres/init.sql       (empty, placeholder for future init hooks)
└── README.md                   top-level (short)
```

---

## Task 0.1 — Top-level README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the file**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: top-level README with dev quickstart"
```

---

## Task 0.2 — Extend .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Overwrite with complete gitignore**

```gitignore
# Superpowers
.superpowers/

# Python
__pycache__/
*.pyc
*.pyo
.venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
*.egg-info/
dist/
build/
backend/.env
backend/.env.local

# Node
node_modules/
.pnpm-store/
frontend/dist/
frontend/.env
frontend/.env.local
frontend/coverage/

# Editor
.DS_Store
.idea/
.vscode/
*.swp

# Ops / local artifacts
ops/postgres-data/
ops/redis-data/
ops/.last-good-sha

# E2E
test-results/
playwright-report/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: extend .gitignore for python, node, ops artifacts"
```

---

## Task 0.3 — Editorconfig

**Files:**
- Create: `.editorconfig`

- [ ] **Step 1: Write**

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 2

[*.py]
indent_size = 4

[Makefile]
indent_style = tab
```

- [ ] **Step 2: Commit**

```bash
git add .editorconfig
git commit -m "chore: add .editorconfig"
```

---

## Task 0.4 — Dev Docker Compose (Postgres + Redis)

**Files:**
- Create: `ops/docker-compose.dev.yml`
- Create: `ops/postgres/init.sql`

- [ ] **Step 1: Write compose file**

```yaml
# ops/docker-compose.dev.yml
services:
  postgres:
    image: postgres:16-alpine
    container_name: hangar-dev-postgres
    environment:
      POSTGRES_USER: hangar
      POSTGRES_PASSWORD: hangar_dev
      POSTGRES_DB: hangar_dev
    ports:
      - "5432:5432"
    volumes:
      - ./postgres-data:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hangar -d hangar_dev"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    container_name: hangar-dev-redis
    command: ["redis-server", "--appendonly", "yes"]
    ports:
      - "6379:6379"
    volumes:
      - ./redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
```

- [ ] **Step 2: Write init.sql placeholder**

```sql
-- ops/postgres/init.sql
-- Runs once on first container start. Alembic manages schema; we only use this
-- for extensions Alembic cannot install.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

- [ ] **Step 3: Start the stack and verify**

```bash
docker compose -f ops/docker-compose.dev.yml up -d
docker compose -f ops/docker-compose.dev.yml ps
```

Expected: both services show `healthy` within ~10s.

```bash
docker exec hangar-dev-postgres psql -U hangar -d hangar_dev -c "SELECT 1"
docker exec hangar-dev-redis redis-cli ping
```

Expected: `1` and `PONG`.

- [ ] **Step 4: Commit**

```bash
git add ops/
git commit -m "chore(ops): dev docker-compose for postgres + redis"
```

---

## Task 0.5 — Backend pyproject + dependencies

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/README.md`
- Create: `backend/.env.example`

- [ ] **Step 1: Write pyproject.toml**

```toml
# backend/pyproject.toml
[project]
name = "hangar-backend"
version = "0.1.0"
description = "Hangar backend API"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "sqlalchemy[asyncio]>=2.0.36",
  "asyncpg>=0.30",
  "alembic>=1.14",
  "pydantic>=2.9",
  "pydantic-settings>=2.6",
  "python-ulid>=3.0",
  "redis[hiredis]>=5.2",
  "httpx>=0.28",
  "cryptography>=44.0",
  "itsdangerous>=2.2",
  "python-multipart>=0.0.17",
  "resend>=2.4",
  "email-validator>=2.2",
]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "pytest-cov>=6.0",
  "httpx>=0.28",
  "ruff>=0.8",
  "mypy>=1.13",
  "sqlalchemy[mypy]>=2.0.36",
  "types-redis",
  "testcontainers[postgres,redis]>=4.8",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["sqlalchemy.ext.mypy.plugin"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --strict-markers"
```

- [ ] **Step 2: Write backend/.env.example**

```ini
# backend/.env.example — copy to backend/.env and fill in for local dev
HANGAR_MASTER_KEY=
HANGAR_DATABASE_URL=postgresql+asyncpg://hangar:hangar_dev@localhost:5432/hangar_dev
HANGAR_REDIS_URL=redis://localhost:6379/0
HANGAR_RESEND_API_KEY=
HANGAR_GITHUB_CLIENT_ID=
HANGAR_GITHUB_CLIENT_SECRET=
HANGAR_BASE_URL=http://localhost:3000
HANGAR_COOKIE_DOMAIN=localhost
HANGAR_SESSION_MAX_AGE=2592000
HANGAR_SENTRY_DSN=
HANGAR_DEV_MODE=1
```

- [ ] **Step 3: Write backend/README.md**

```markdown
# Hangar Backend

FastAPI + SQLAlchemy-async + Alembic + Postgres + Redis.

## Dev

```bash
uv sync
cp .env.example .env    # fill in HANGAR_MASTER_KEY (see below) + others
uv run uvicorn app.main:app --reload --port 8000
```

### Generate a master key

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Paste into `HANGAR_MASTER_KEY` in `.env`.

## Test

```bash
uv run pytest
```
```

- [ ] **Step 4: Run uv sync to lock dependencies**

```bash
cd backend && uv sync
```

Expected: creates `backend/.venv/` and `backend/uv.lock`.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/README.md backend/.env.example backend/uv.lock
git commit -m "feat(backend): pyproject with FastAPI + async SQLAlchemy deps"
```

---

## Task 0.6 — Minimal FastAPI app with /healthz

**Files:**
- Create: `backend/app/__init__.py` (empty)
- Create: `backend/app/main.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/__init__.py` (empty) and `backend/tests/test_healthz.py`:

```python
# backend/tests/test_healthz.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_healthz_ok() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "version" in body
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_healthz.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/__init__.py
```

```python
# backend/app/main.py
from fastapi import FastAPI

app = FastAPI(title="Hangar", version="0.1.0")


@app.get("/api/v1/healthz")
async def healthz() -> dict[str, object]:
    return {"ok": True, "version": app.version, "db": "unknown", "redis": "unknown"}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_healthz.py -v
```

Expected: `1 passed`.

- [ ] **Step 5: Start the server manually and curl it**

```bash
uv run uvicorn app.main:app --port 8000 &
sleep 2
curl -s http://localhost:8000/api/v1/healthz
kill %1 2>/dev/null || true
```

Expected: `{"ok":true,"version":"0.1.0","db":"unknown","redis":"unknown"}`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ backend/tests/
git commit -m "feat(backend): minimal FastAPI app with /healthz endpoint"
```

---

## Task 0.7 — Frontend scaffold (Vite + Vue 3 + TS)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/env.d.ts`
- Create: `frontend/README.md`

- [ ] **Step 1: Write package.json**

```json
{
  "name": "hangar-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "typecheck": "vue-tsc --noEmit",
    "lint": "eslint . --ext .ts,.vue --max-warnings 0",
    "gen:api": "openapi-typescript http://localhost:8000/api/v1/openapi.json -o src/api/types.gen.ts"
  },
  "dependencies": {
    "vue": "^3.5.13",
    "vue-router": "^4.5.0",
    "pinia": "^2.3.0"
  },
  "devDependencies": {
    "@types/node": "^22.10.0",
    "@vitejs/plugin-vue": "^5.2.1",
    "@vue/tsconfig": "^0.7.0",
    "eslint": "^9.16.0",
    "eslint-plugin-vue": "^9.32.0",
    "jsdom": "^25.0.1",
    "msw": "^2.6.8",
    "openapi-typescript": "^7.4.4",
    "typescript": "~5.7.2",
    "vite": "^6.0.0",
    "vitest": "^2.1.6",
    "vue-tsc": "^2.1.10"
  }
}
```

- [ ] **Step 2: Write vite.config.ts**

```typescript
// frontend/vite.config.ts
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: false },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
```

- [ ] **Step 3: Write tsconfig.json + tsconfig.node.json**

```json
// frontend/tsconfig.json
{
  "extends": "@vue/tsconfig/tsconfig.dom.json",
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "allowImportingTsExtensions": false,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] },
    "types": ["vite/client", "node", "vitest/globals"]
  },
  "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.vue"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

```json
// frontend/tsconfig.node.json
{
  "compilerOptions": {
    "composite": true,
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Write index.html + src files**

```html
<!-- frontend/index.html -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Hangar</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

```typescript
// frontend/src/main.ts
import { createApp } from "vue";
import App from "./App.vue";

createApp(App).mount("#app");
```

```vue
<!-- frontend/src/App.vue -->
<script setup lang="ts"></script>

<template>
  <main>
    <h1>Hangar</h1>
    <p>Scaffold OK.</p>
  </main>
</template>
```

```typescript
// frontend/src/env.d.ts
/// <reference types="vite/client" />

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<object, object, unknown>;
  export default component;
}
```

- [ ] **Step 5: Write frontend/README.md**

```markdown
# Hangar Frontend

Vue 3 + TS + Vite + Pinia.

## Dev

```bash
pnpm install
pnpm dev
```

Opens http://localhost:3000 with `/api` proxied to backend at :8000.
```

- [ ] **Step 6: Install deps and start dev server to verify**

```bash
cd frontend && pnpm install
pnpm dev &
sleep 3
curl -s http://localhost:3000/ | head -5
kill %1 2>/dev/null || true
```

Expected: HTML containing `<title>Hangar</title>`.

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): Vue 3 + TS + Vite scaffold with /api proxy"
```

---

## Task 0.8 — CI pipeline skeleton

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the CI file**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  backend:
    name: Backend
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: hangar
          POSTGRES_PASSWORD: hangar_ci
          POSTGRES_DB: hangar_ci
        ports: ["5432:5432"]
        options: >-
          --health-cmd="pg_isready -U hangar -d hangar_ci"
          --health-interval=5s --health-timeout=3s --health-retries=10
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: --health-cmd="redis-cli ping" --health-interval=5s --health-retries=10
    env:
      HANGAR_DATABASE_URL: postgresql+asyncpg://hangar:hangar_ci@localhost:5432/hangar_ci
      HANGAR_REDIS_URL: redis://localhost:6379/0
      HANGAR_MASTER_KEY: test_master_key_32bytes_base64url_AAAAAAAAAAAAAAAAAAAAAAAA
      HANGAR_RESEND_API_KEY: test_fake
      HANGAR_GITHUB_CLIENT_ID: test_fake
      HANGAR_GITHUB_CLIENT_SECRET: test_fake
      HANGAR_BASE_URL: http://localhost:3000
      HANGAR_COOKIE_DOMAIN: localhost
      HANGAR_SESSION_MAX_AGE: "2592000"
      HANGAR_DEV_MODE: "1"
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with: { enable-cache: true }
      - run: uv python install 3.12
      - name: Install
        working-directory: backend
        run: uv sync
      - name: Ruff
        working-directory: backend
        run: uv run ruff check .
      - name: Mypy
        working-directory: backend
        run: uv run mypy app
      - name: Pytest
        working-directory: backend
        run: uv run pytest -v

  frontend:
    name: Frontend
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with: { version: 9 }
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: pnpm, cache-dependency-path: frontend/pnpm-lock.yaml }
      - name: Install
        working-directory: frontend
        run: pnpm install --frozen-lockfile
      - name: Typecheck
        working-directory: frontend
        run: pnpm typecheck
      - name: Test
        working-directory: frontend
        run: pnpm test --run
      - name: Build
        working-directory: frontend
        run: pnpm build
```

- [ ] **Step 2: Commit**

```bash
git add .github/
git commit -m "ci: backend (ruff+mypy+pytest) and frontend (typecheck+test+build) pipelines"
```

- [ ] **Step 3: Run the full checks locally**

```bash
cd backend && uv run ruff check . && uv run mypy app && uv run pytest -v
cd ../frontend && pnpm typecheck && pnpm build
```

Expected: all four commands exit 0.

---

## Phase 0 complete when

- [ ] `docker compose -f ops/docker-compose.dev.yml up -d` brings Postgres + Redis to healthy.
- [ ] `uv run pytest` in `backend/` passes 1 test (`test_healthz_ok`).
- [ ] `pnpm dev` in `frontend/` serves `http://localhost:3000`.
- [ ] `pnpm build` in `frontend/` produces `frontend/dist/`.
- [ ] `uv run ruff check .` and `uv run mypy app` pass with no errors.
- [ ] First CI run on `main` is green.
- [ ] Last commit on branch: `ci: backend (ruff+mypy+pytest) and frontend (typecheck+test+build) pipelines`.

Phase 1 (database foundation) depends on this skeleton.
