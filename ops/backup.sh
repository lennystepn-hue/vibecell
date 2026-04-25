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
docker compose --env-file /etc/hangar/hangar.env \
  -f /srv/hangar/ops/docker-compose.prod.yml exec -T postgres \
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

# ---------------------------------------------------------------------------
# Off-site replication (Backblaze B2).
#
# A backup that lives only on the same VPS as the database is one disk
# failure away from total loss. This block syncs the freshly-written
# daily file to B2 if credentials are configured. If they're NOT set,
# the script just no-ops (no error) so existing self-hosters aren't
# surprised by a sudden hard requirement.
#
# Required env (set in /etc/hangar/hangar.env):
#   BACKUP_B2_KEY_ID         — B2 application key ID
#   BACKUP_B2_APPLICATION_KEY — B2 application key secret
#   BACKUP_B2_BUCKET         — bucket name (e.g. "vibecell-backups")
#
# Tooling: uses rclone (apt install rclone) configured with a remote
# named "b2" pointing at the credentials above. The rclone.conf is
# generated on first run if absent.
# ---------------------------------------------------------------------------

if [ -n "${BACKUP_B2_BUCKET:-}" ] && [ -n "${BACKUP_B2_KEY_ID:-}" ] && [ -n "${BACKUP_B2_APPLICATION_KEY:-}" ]; then
  if ! command -v rclone >/dev/null 2>&1; then
    echo "[$(date -Is)] WARN: BACKUP_B2_BUCKET set but rclone not installed — skipping off-site sync"
  else
    RCLONE_CONFIG="/root/.config/rclone/rclone.conf"
    mkdir -p "$(dirname "$RCLONE_CONFIG")"
    if [ ! -f "$RCLONE_CONFIG" ] || ! grep -q "^\[b2\]" "$RCLONE_CONFIG"; then
      cat >> "$RCLONE_CONFIG" <<EOF
[b2]
type = b2
account = $BACKUP_B2_KEY_ID
key = $BACKUP_B2_APPLICATION_KEY
hard_delete = false
EOF
      chmod 600 "$RCLONE_CONFIG"
    fi

    echo "[$(date -Is)] syncing $DAILY_FILE to b2:$BACKUP_B2_BUCKET/daily/"
    rclone copy "$DAILY_FILE" "b2:$BACKUP_B2_BUCKET/daily/" --quiet
    if [[ "$DAY_OF_WEEK" == "7" ]]; then
      rclone copy "$BACKUP_DIR/weekly/hangar-week-$DATE.sql.gz" "b2:$BACKUP_B2_BUCKET/weekly/" --quiet
    fi
    if [[ "$DAY_OF_MONTH" == "01" ]]; then
      rclone copy "$BACKUP_DIR/monthly/hangar-month-$DATE.sql.gz" "b2:$BACKUP_B2_BUCKET/monthly/" --quiet
    fi
    echo "[$(date -Is)] off-site sync ok"
  fi
fi
