#!/bin/bash
# Hangar production deploy.
# Usage: ./deploy.sh [sha]
# Runs on the target server at /srv/hangar.

set -euo pipefail

cd "$(dirname "$0")/.."

SHA="${1:-$(date +%s)}"
export HANGAR_SHA="$SHA"

# /etc/hangar/hangar.env holds POSTGRES_PASSWORD etc. — docker compose needs
# --env-file for shell-style ${VAR} interpolation in the compose file.
ENV_FILE="${HANGAR_ENV_FILE:-/etc/hangar/hangar.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "==> FATAL: $ENV_FILE not found. Create it (see docs/deploy.md)."
  exit 1
fi

COMPOSE="docker compose --env-file $ENV_FILE -f ops/docker-compose.prod.yml"

echo "==> Deploying Hangar at SHA=$SHA"

# 1. Build images
echo "==> Building backend image"
$COMPOSE build backend

echo "==> Building frontend image"
$COMPOSE build frontend

# 2. Bring up dependencies (postgres + redis)
echo "==> Starting postgres + redis"
$COMPOSE up -d postgres redis

# Wait for postgres healthy
echo "==> Waiting for postgres to be healthy"
for i in {1..30}; do
  if $COMPOSE ps postgres --format json | grep -q '"Health":"healthy"'; then
    break
  fi
  sleep 1
done

# 3. Run migrations
echo "==> Running Alembic migrations"
$COMPOSE run --rm backend alembic upgrade head

# 4. Roll out backend + frontend + nginx
echo "==> Rolling out app containers"
$COMPOSE up -d backend frontend nginx

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
    $COMPOSE up -d backend frontend nginx
  fi
  exit 1
fi

# 6. Post-deploy cleanup. Every backend image is ~3GB and we build one per
# deploy — without pruning, even half a day of iterative deploys fills a
# 38GB root disk and postgres panics on checkpoint writes. Two repeats of
# that incident is enough to convince us the window has to be tight.
echo "==> Pruning old Docker images + build cache"
docker image prune -a --force --filter "until=24h" > /dev/null 2>&1 || true
docker builder prune -f --filter "until=24h" > /dev/null 2>&1 || true

# Hard-stop if disk is still under pressure: prune EVERYTHING dangling
# (no time filter) and surface it loudly.
DISK_PCT=$(df / --output=pcent | tail -1 | tr -d ' %')
if [[ -n "$DISK_PCT" && "$DISK_PCT" -gt 80 ]]; then
  echo "==> WARNING: root disk ${DISK_PCT}% full — running aggressive prune"
  docker image prune -a --force > /dev/null 2>&1 || true
  docker builder prune -a -f > /dev/null 2>&1 || true
  DISK_PCT=$(df / --output=pcent | tail -1 | tr -d ' %')
  echo "==> Disk after aggressive prune: ${DISK_PCT}%"
fi
