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
