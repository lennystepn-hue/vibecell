#!/bin/bash
# Hangar Postgres restore drill.
#
# Verifies that the latest daily backup is actually restorable end-to-end
# by spinning up a throwaway Postgres container, restoring into it, and
# asserting that the schema + at least one row from `users` came through.
#
# Cron: 0 4 1 * * /srv/hangar/ops/restore-drill.sh >> /var/log/hangar-restore-drill.log 2>&1
#
# Why this matters: a backup nobody has restored is a hope, not a backup.
# This drill catches silent corruption (truncated dumps, broken schema
# transitions, expired credentials) before they become a 3am emergency.
#
# Exit codes:
#   0 — drill passed
#   1 — no backup files found
#   2 — restore failed (gunzip / psql error)
#   3 — schema check failed (users table missing or empty)
set -euo pipefail

BACKUP_DIR="/srv/hangar/backups/daily"
LATEST=$(ls -1t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | head -n1 || true)

if [ -z "$LATEST" ]; then
  echo "[$(date -Is)] DRILL FAILED: no backups in $BACKUP_DIR"
  exit 1
fi

echo "[$(date -Is)] drilling against $LATEST"
SIZE=$(du -h "$LATEST" | cut -f1)

DRILL_NAME="hangar-restore-drill-$(date +%s)"
DRILL_PASSWORD="drill-$(openssl rand -hex 8)"

# Spin up a throwaway Postgres
docker run --rm -d \
  --name "$DRILL_NAME" \
  -e POSTGRES_PASSWORD="$DRILL_PASSWORD" \
  -e POSTGRES_USER=hangar \
  -e POSTGRES_DB=hangar \
  postgres:16-alpine \
  > /dev/null

# Wait for it to accept connections
for i in $(seq 1 30); do
  if docker exec "$DRILL_NAME" pg_isready -U hangar -d hangar > /dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$i" = "30" ]; then
    echo "[$(date -Is)] DRILL FAILED: drill container never became ready"
    docker stop "$DRILL_NAME" > /dev/null
    exit 2
  fi
done

# Restore
if ! gunzip -c "$LATEST" | docker exec -i "$DRILL_NAME" psql -U hangar -d hangar > /tmp/restore-drill.out 2>&1; then
  echo "[$(date -Is)] DRILL FAILED: restore command errored"
  echo "--- last 50 lines of psql output ---"
  tail -50 /tmp/restore-drill.out
  docker stop "$DRILL_NAME" > /dev/null
  exit 2
fi

# Schema sanity check — users table exists and has at least one row
USER_COUNT=$(docker exec "$DRILL_NAME" psql -U hangar -d hangar -tAc \
  "SELECT count(*) FROM users" 2>/dev/null || echo "0")

PROJECT_COUNT=$(docker exec "$DRILL_NAME" psql -U hangar -d hangar -tAc \
  "SELECT count(*) FROM projects" 2>/dev/null || echo "0")

# Cleanup
docker stop "$DRILL_NAME" > /dev/null

if [ "$USER_COUNT" -lt 1 ]; then
  echo "[$(date -Is)] DRILL FAILED: 0 users in restored backup ($SIZE)"
  exit 3
fi

echo "[$(date -Is)] DRILL PASSED — backup $SIZE, users=$USER_COUNT, projects=$PROJECT_COUNT"
