# Phase 17 — Production Deploy

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Ship Hangar to a reachable production URL on the existing staging VPS. Full stack behind a reverse proxy, backups, health check, deploy script.

**Prerequisite:** Phase 16 complete (HEAD ≥ `7848776`).

**Context on staging VPS state:** `89.167.111.89` (Hetzner Helsinki, 4GB, Ubuntu 24.04) already runs Docker, with existing services (`agentready-nginx` holding ports 80/443, plus `giftmakr-*` containers). Hangar's dev Postgres+Redis containers are live on `:5432`/`:6379`. Backend has been running on `:8000` ad-hoc. We bring this to a proper compose stack.

---

## Strategy

1. **Hangar runs as its own compose project** in `/srv/hangar` with 4 services: `postgres`, `redis`, `backend`, `nginx`.
2. **Frontend** is built locally (or on server), output in `frontend/dist/`, served as static files by the Hangar-scoped `nginx` container.
3. **Public port:** Hangar `nginx` binds to `:8080` externally (to avoid collision with the existing `agentready-nginx` on 80/443). User will point `hangar.dev` at 89.167.111.89 and either:
   - Add a server block to the existing `agentready-nginx` that proxies to `:8080`, OR
   - Route through Cloudflare / another edge
4. **Backups:** nightly `pg_dump` → encrypted tar, retention 7/4/3 (daily/weekly/monthly), local for v1 (offsite offload is Phase 5+ territory).
5. **deploy.sh:** single script on the server, pulls the latest code from a git remote (none yet — so v1 uses tar-pipe from local).

---

## Files

```
backend/
├── Dockerfile                     Python 3.12-slim + uv + app
└── .dockerignore
frontend/
├── Dockerfile                     multi-stage: build → nginx static
└── .dockerignore
ops/
├── docker-compose.prod.yml
├── nginx/hangar.conf              reverse proxy config for the Hangar nginx
└── deploy.sh                      pulls, builds, migrates, restarts, health-checks
docs/
└── deploy.md                      production runbook
```

---

## Task 17.1 — Backend Dockerfile

**File:** `backend/Dockerfile`

```dockerfile
FROM python:3.12-slim AS builder

# uv from astral.sh — pinned
COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Install deps first for better caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy app source
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

RUN uv sync --frozen --no-dev

# ----

FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Run as non-root
RUN useradd -r -u 1000 -g root hangar && chown -R hangar:root /app
USER hangar

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/v1/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

**File:** `backend/.dockerignore`

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.mypy_cache/
tests/
.env
.env.local
```

Commit: `feat(backend): production Dockerfile with uv + non-root runtime + healthcheck`

---

## Task 17.2 — Frontend Dockerfile

**File:** `frontend/Dockerfile`

```dockerfile
FROM node:22-alpine AS builder

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . ./
RUN pnpm build

# ----

FROM nginx:1.27-alpine AS runtime

# Replace default nginx config
RUN rm /etc/nginx/conf.d/default.conf
COPY <<'EOF' /etc/nginx/conf.d/app.conf
server {
  listen 80 default_server;
  server_name _;
  root /usr/share/nginx/html;
  index index.html;

  # Long-cache hashed assets
  location ~* \.(?:css|js|woff2|svg|png|jpg|jpeg|gif|ico)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    try_files $uri =404;
  }

  # SPA fallback for client-side routes
  location / {
    try_files $uri $uri/ /index.html;
  }
}
EOF

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://127.0.0.1/ > /dev/null || exit 1
```

**File:** `frontend/.dockerignore`

```
node_modules/
dist/
.pnpm-store/
coverage/
test-results/
playwright-report/
e2e/
**/*.spec.ts
**/__tests__/
```

Commit: `feat(frontend): production Dockerfile (multi-stage build → nginx static)`

---

## Task 17.3 — Hangar reverse proxy + docker-compose.prod.yml

**File:** `ops/nginx/hangar.conf`

```nginx
upstream hangar_backend {
  server backend:8000;
}

upstream hangar_frontend {
  server frontend:80;
}

server {
  listen 80 default_server;
  server_name _;

  client_max_body_size 10M;

  # Backend API
  location /api/ {
    proxy_pass http://hangar_backend;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 60s;
  }

  # Static frontend
  location / {
    proxy_pass http://hangar_frontend;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
}
```

**File:** `ops/docker-compose.prod.yml`

```yaml
name: hangar

services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-hangar}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-hangar}
    volumes:
      - pg-data:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-hangar} -d ${POSTGRES_DB:-hangar}"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 10

  backend:
    image: hangar-backend:${HANGAR_SHA:-latest}
    build:
      context: ../backend
    restart: unless-stopped
    env_file:
      - /etc/hangar/hangar.env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8000/api/v1/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3

  frontend:
    image: hangar-frontend:${HANGAR_SHA:-latest}
    build:
      context: ../frontend
    restart: unless-stopped
    depends_on:
      - backend

  nginx:
    image: nginx:1.27-alpine
    restart: unless-stopped
    ports:
      - "8080:80"
    volumes:
      - ./nginx/hangar.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - backend
      - frontend

volumes:
  pg-data:
  redis-data:
```

Commit: `feat(ops): docker-compose.prod.yml + nginx reverse proxy config`

---

## Task 17.4 — deploy.sh

**File:** `ops/deploy.sh`

```bash
#!/bin/bash
# Hangar production deploy.
# Usage: ./deploy.sh [sha]
# Runs on the target server at /srv/hangar.

set -euo pipefail

cd "$(dirname "$0")/.."

SHA="${1:-$(date +%s)}"
export HANGAR_SHA="$SHA"

echo "==> Deploying Hangar at SHA=$SHA"

# 1. Build images
echo "==> Building backend image"
docker compose -f ops/docker-compose.prod.yml build backend

echo "==> Building frontend image"
docker compose -f ops/docker-compose.prod.yml build frontend

# 2. Bring up dependencies (postgres + redis)
echo "==> Starting postgres + redis"
docker compose -f ops/docker-compose.prod.yml up -d postgres redis

# Wait for postgres healthy
echo "==> Waiting for postgres to be healthy"
for i in {1..30}; do
  if docker compose -f ops/docker-compose.prod.yml ps postgres --format json \
      | grep -q '"Health":"healthy"'; then
    break
  fi
  sleep 1
done

# 3. Run migrations
echo "==> Running Alembic migrations"
docker compose -f ops/docker-compose.prod.yml run --rm backend alembic upgrade head

# 4. Roll out backend + frontend + nginx
echo "==> Rolling out app containers"
docker compose -f ops/docker-compose.prod.yml up -d backend frontend nginx

# 5. Health check
sleep 5
echo "==> Health check"
if curl -fsS http://localhost:8080/api/v1/healthz > /dev/null; then
  echo "$SHA" > /srv/hangar/.last-good-sha
  echo "==> OK — deployed $SHA"
else
  PREV="$(cat /srv/hangar/.last-good-sha 2>/dev/null || echo 'unknown')"
  echo "==> FAILED health check. Previous good SHA: $PREV"
  echo "==> Rolling back"
  if [[ "$PREV" != "unknown" ]]; then
    export HANGAR_SHA="$PREV"
    docker compose -f ops/docker-compose.prod.yml up -d backend frontend nginx
  fi
  exit 1
fi
```

Make executable: `chmod +x ops/deploy.sh`.

Commit: `feat(ops): deploy.sh (build → migrate → rollout → health → rollback on fail)`

---

## Task 17.5 — Backup cron

**File:** `ops/backup.sh`

```bash
#!/bin/bash
# Hangar nightly Postgres backup.
# Cron: 0 3 * * * /srv/hangar/ops/backup.sh >> /var/log/hangar-backup.log 2>&1
set -euo pipefail

BACKUP_DIR="/srv/hangar/backups"
mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly" "$BACKUP_DIR/monthly"

DATE="$(date +%F)"
DAY_OF_WEEK="$(date +%u)"
DAY_OF_MONTH="$(date +%d)"

DAILY_FILE="$BACKUP_DIR/daily/hangar-$DATE.sql.gz"

echo "[$(date -Is)] dumping to $DAILY_FILE"
docker compose -f /srv/hangar/ops/docker-compose.prod.yml exec -T postgres \
  pg_dump -U hangar hangar \
  | gzip -9 > "$DAILY_FILE"

# Retention:
#   daily:  keep last 7
#   weekly: snapshot on Sunday, keep last 4
#   monthly: snapshot on 1st, keep last 3
find "$BACKUP_DIR/daily/" -type f -name "*.sql.gz" -mtime +7 -delete

if [[ "$DAY_OF_WEEK" == "7" ]]; then
  cp "$DAILY_FILE" "$BACKUP_DIR/weekly/hangar-week-$DATE.sql.gz"
  find "$BACKUP_DIR/weekly/" -type f -name "*.sql.gz" -mtime +28 -delete
fi

if [[ "$DAY_OF_MONTH" == "01" ]]; then
  cp "$DAILY_FILE" "$BACKUP_DIR/monthly/hangar-month-$DATE.sql.gz"
  find "$BACKUP_DIR/monthly/" -type f -name "*.sql.gz" -mtime +93 -delete
fi

SIZE="$(du -h "$DAILY_FILE" | cut -f1)"
echo "[$(date -Is)] done — $SIZE"
```

Make executable. Document cron install in deploy.md below.

Commit: `feat(ops): backup.sh (daily pg_dump + 7/4/3 retention)`

---

## Task 17.6 — Deploy runbook

**File:** `docs/deploy.md`

```markdown
# Production deploy — Hangar

Staging + first production instance: `89.167.111.89` (Hetzner Helsinki, 4 GB).

## Prerequisites on the server

- Docker + Docker Compose v2 (already installed).
- `/etc/hangar/hangar.env` with production secrets.
- DNS: point `hangar.dev` (and `www.hangar.dev`) at the server's IP.

### Server environment file

Create `/etc/hangar/hangar.env` (root:root, chmod 600):

```ini
HANGAR_MASTER_KEY=<generate via: python -c "import secrets; print(secrets.token_urlsafe(32))">
HANGAR_DATABASE_URL=postgresql+asyncpg://hangar:<POSTGRES_PASSWORD>@postgres:5432/hangar
HANGAR_REDIS_URL=redis://redis:6379/0
HANGAR_RESEND_API_KEY=re_...
HANGAR_GITHUB_CLIENT_ID=...
HANGAR_GITHUB_CLIENT_SECRET=...
HANGAR_BASE_URL=https://hangar.dev
HANGAR_COOKIE_DOMAIN=hangar.dev
HANGAR_SESSION_MAX_AGE=2592000
HANGAR_SENTRY_DSN=
HANGAR_DEV_MODE=0

# Postgres container env
POSTGRES_USER=hangar
POSTGRES_PASSWORD=<strong random>
POSTGRES_DB=hangar
```

## First-time deploy

On your laptop:

```bash
# 1. Sync code to server
tar --exclude='.git' --exclude='node_modules' --exclude='.venv' \
    --exclude='dist' --exclude='.superpowers' -cf - . \
  | ssh root@89.167.111.89 "mkdir -p /srv/hangar && cd /srv/hangar && tar -xf -"

# 2. Run deploy on server
ssh root@89.167.111.89 "cd /srv/hangar && ./ops/deploy.sh $(git rev-parse --short HEAD)"
```

Verify: `curl http://89.167.111.89:8080/api/v1/healthz` → `{"ok":true,...}`.

## Expose hangar.dev

Two options:

### Option 1: Route through existing `agentready-nginx`

The server already runs `agentready-nginx` on ports 80/443. Add a server
block that proxies `hangar.dev` to `localhost:8080`:

```nginx
server {
  listen 443 ssl http2;
  server_name hangar.dev www.hangar.dev;
  ssl_certificate /etc/letsencrypt/live/hangar.dev/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/hangar.dev/privkey.pem;

  location / {
    proxy_pass http://localhost:8080;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}

server {
  listen 80;
  server_name hangar.dev www.hangar.dev;
  return 301 https://$host$request_uri;
}
```

Issue cert: `certbot --nginx -d hangar.dev -d www.hangar.dev`.

### Option 2: Cloudflare proxy

Point `hangar.dev` A record at 89.167.111.89, orange-cloud on. Cloudflare
terminates TLS; backend sees HTTP. Set an origin rule so Cloudflare pulls
from `http://89.167.111.89:8080`.

## Subsequent deploys

```bash
ssh root@89.167.111.89 "cd /srv/hangar && git pull && ./ops/deploy.sh $(git rev-parse --short HEAD)"
```

(Assumes the server has been set up with a git remote. For v1 we tar-pipe
over SSH instead.)

## Backups

Install the cron (once):

```bash
ssh root@89.167.111.89 'chmod +x /srv/hangar/ops/backup.sh && echo "0 3 * * * /srv/hangar/ops/backup.sh >> /var/log/hangar-backup.log 2>&1" | crontab -'
```

Backups land in `/srv/hangar/backups/{daily,weekly,monthly}/`.

### Manual restore

```bash
docker compose -f /srv/hangar/ops/docker-compose.prod.yml exec -T postgres \
  psql -U hangar -d hangar < /srv/hangar/backups/daily/hangar-2026-04-20.sql.gz.decompressed
```

Or in-place:

```bash
gunzip -c /srv/hangar/backups/daily/hangar-YYYY-MM-DD.sql.gz \
  | docker compose -f /srv/hangar/ops/docker-compose.prod.yml exec -T postgres \
    psql -U hangar -d hangar
```

## Uptime monitoring

Point an external pinger (UptimeRobot free tier works) at:

- `https://hangar.dev/api/v1/healthz` — must return `{"ok": true}` with status 200.
- Alert threshold: down for > 2 checks in a row (10 min).

## Rollback

`deploy.sh` auto-rolls back on health-check fail. Manual rollback:

```bash
ssh root@89.167.111.89 "cd /srv/hangar && HANGAR_SHA=<prev-sha> docker compose -f ops/docker-compose.prod.yml up -d backend frontend nginx"
```

## Secret rotation

1. Edit `/etc/hangar/hangar.env` on the server (root:root, mode 600).
2. `docker compose -f ops/docker-compose.prod.yml restart backend`.
3. Verify via `/api/v1/healthz`.
```

Commit: `docs: production deploy runbook (setup, deploy, DNS, backups, rollback)`

---

## Task 17.7 — First production deploy on staging (verification)

Run the full deploy sequence on the staging VPS as the first real production run.

```bash
# Sync code
cd C:/Users/ender/OneDrive/Desktop/Hangar
tar --exclude='.git' --exclude='node_modules' --exclude='.venv' --exclude='dist' --exclude='.superpowers' -cf - . \
  | ssh root@89.167.111.89 "cd /srv/hangar && tar -xf -"

# Write env file if not present (this assumes the existing ad-hoc env from Phase 16
# is moved to /etc/hangar/hangar.env)
ssh root@89.167.111.89 'mkdir -p /etc/hangar && [ -f /etc/hangar/hangar.env ] || cat > /etc/hangar/hangar.env <<EOF
HANGAR_MASTER_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(32))")
HANGAR_DATABASE_URL=postgresql+asyncpg://hangar:hangar_prod_$(openssl rand -hex 8)@postgres:5432/hangar
HANGAR_REDIS_URL=redis://redis:6379/0
HANGAR_RESEND_API_KEY=test
HANGAR_GITHUB_CLIENT_ID=test
HANGAR_GITHUB_CLIENT_SECRET=test
HANGAR_BASE_URL=http://89.167.111.89:8080
HANGAR_COOKIE_DOMAIN=
HANGAR_SESSION_MAX_AGE=2592000
HANGAR_DEV_MODE=0
POSTGRES_USER=hangar
POSTGRES_PASSWORD=hangar_prod
POSTGRES_DB=hangar
EOF
chmod 600 /etc/hangar/hangar.env'

# Kill the ad-hoc uvicorn so port 8000 isn't claimed
ssh root@89.167.111.89 'pkill -f "uvicorn app.main" 2>/dev/null || true'

# Stop the dev docker-compose so its postgres/redis don't collide
ssh root@89.167.111.89 'cd /srv/hangar && docker compose -f ops/docker-compose.dev.yml down 2>/dev/null || true'

# Run production deploy
ssh root@89.167.111.89 "cd /srv/hangar && ./ops/deploy.sh $(git rev-parse --short HEAD)"

# Verify
curl -fsS http://89.167.111.89:8080/api/v1/healthz
curl -fsS http://89.167.111.89:8080/ | head -20
```

Expected: first curl returns `{"ok":true,...}`, second returns the Vue SPA HTML.

**Manual end-to-end smoke test:**

Open `http://89.167.111.89:8080` in a browser. You should see the Cockpit-themed login page.
Enter your email, click Send. Check `/var/log` on server for the magic link (dev-mode is off, so
email actually gets sent via Resend — confirm token arrives).

If no Resend key, temporarily set `HANGAR_DEV_MODE=1` in the env file + restart backend:

```bash
ssh root@89.167.111.89 "sed -i 's/HANGAR_DEV_MODE=0/HANGAR_DEV_MODE=1/' /etc/hangar/hangar.env && docker compose -f /srv/hangar/ops/docker-compose.prod.yml restart backend"
```

Then `ssh root@89.167.111.89 'docker compose -f /srv/hangar/ops/docker-compose.prod.yml logs backend | grep "DEV MAGIC LINK"'` pulls the verify URL. Open it in the browser. You should land on `/p`, empty hangar.

Commit: `chore(ops): first production deploy verified on staging VPS`

(This commit is a no-op code change — it's just the marker for the successful deploy. If you prefer not to commit a marker, skip it; the phase is still complete.)

---

## Phase 17 complete when

- [ ] `docker compose -f ops/docker-compose.prod.yml ps` shows 4 healthy services.
- [ ] `curl http://89.167.111.89:8080/api/v1/healthz` returns `{"ok":true}`.
- [ ] Browser-opening the root URL renders the login page.
- [ ] Magic-link sign-in works end-to-end (dev or real Resend).
- [ ] Creating a project and reloading works.
- [ ] Backup cron scheduled and first run verified manually.
- [ ] 6 commits on main (17.1–17.6) plus optional 17.7 deploy marker.

**After this phase:** Hangar Spec 1 is fully shipped. hangar.dev can be pointed at the server when DNS + edge are ready.
