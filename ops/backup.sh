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
