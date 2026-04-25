# Postgres Backup & Restore Runbook

> Copy-pasteable recovery for vibecell.dev's Postgres in case of disk failure,
> data corruption, accidental drop, or migration-gone-wrong. Bookmark this.

## Quick reference

| Want to... | Run |
|---|---|
| Manual backup right now | `ssh root@89.167.111.89 /srv/hangar/ops/backup.sh` |
| Verify latest backup is restorable | `ssh root@89.167.111.89 /srv/hangar/ops/restore-drill.sh` |
| Full restore from latest local backup | See "Restore" below |
| Pull a backup from B2 to your laptop | `rclone copy b2:vibecell-backups/daily/<file> .` |

## Backup schedule (current, per `/srv/hangar/ops/backup.sh`)

```
Daily   03:00 UTC  → /srv/hangar/backups/daily/   (last 7 days)
Weekly  Sunday     → /srv/hangar/backups/weekly/  (last 4 weeks)
Monthly 1st day    → /srv/hangar/backups/monthly/ (last 3 months)
```

If `BACKUP_B2_BUCKET` + `BACKUP_B2_KEY_ID` + `BACKUP_B2_APPLICATION_KEY` are
set in `/etc/hangar/hangar.env`, the same files are pushed to Backblaze B2
under matching prefixes immediately after each local write.

If those env vars are NOT set, **off-site sync silently skips**. Add them
ASAP — a single-VPS backup is hope, not a backup.

## Restore drill (monthly, automated)

`ops/restore-drill.sh` runs on the 1st of every month at 04:00 UTC via
crontab. It spins up a throwaway Postgres container, restores the latest
daily dump into it, asserts that `users` and `projects` have rows, then
tears down. Logs to `/var/log/hangar-restore-drill.log`.

A drill **MUST** run successfully at least once. Run it manually after
this runbook lands:

```bash
ssh root@89.167.111.89 /srv/hangar/ops/restore-drill.sh
# expect last line: "DRILL PASSED — backup <SIZE>, users=<N>, projects=<M>"
```

If it fails, fix it before considering Sprint A done. **Don't ship paying
users on a backup regime nobody has restored from.**

## Crontab setup (one-time, manual)

SSH to the prod VPS and run:

```bash
ssh root@89.167.111.89
crontab -l   # check if entries exist
crontab -e   # add these:
0 3 * * * /srv/hangar/ops/backup.sh >> /var/log/hangar-backup.log 2>&1
0 4 1 * * /srv/hangar/ops/restore-drill.sh >> /var/log/hangar-restore-drill.log 2>&1
```

Verify after 24h:

```bash
ssh root@89.167.111.89 ls -lh /srv/hangar/backups/daily/ | tail -3
ssh root@89.167.111.89 tail -20 /var/log/hangar-backup.log
```

## Restore (full, from local backup)

**Use this only in genuine "we lost data" situations.** Scenarios:
- VPS rebuilt from scratch
- Postgres data dir corrupted
- Production migration trashed real rows
- "Oh no I dropped the prod schema"

```bash
ssh root@89.167.111.89

# 1. Identify the file you want to restore (use the LATEST that pre-dates
#    the bad event — not necessarily today's).
ls -lht /srv/hangar/backups/daily/ | head -10

LATEST=/srv/hangar/backups/daily/hangar-2026-04-25.sql.gz   # ← edit me

# 2. Stop the app to prevent writes during restore.
cd /srv/hangar
docker compose -f ops/docker-compose.prod.yml stop backend

# 3. Drop and recreate the schema. THIS WIPES CURRENT DATA — confirm you have
#    a fallback plan if restore fails.
docker compose -f ops/docker-compose.prod.yml exec -T postgres \
  psql -U hangar -d hangar -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# 4. Restore.
gunzip -c "$LATEST" | docker compose -f ops/docker-compose.prod.yml exec -T postgres \
  psql -U hangar -d hangar

# 5. Smoke check.
docker compose -f ops/docker-compose.prod.yml exec postgres \
  psql -U hangar -d hangar -c "SELECT count(*) FROM users;"
docker compose -f ops/docker-compose.prod.yml exec postgres \
  psql -U hangar -d hangar -c "SELECT count(*) FROM projects;"

# 6. Bring backend back up.
docker compose -f ops/docker-compose.prod.yml start backend

# 7. Hit /healthz, then poke around the dashboard.
curl https://vibecell.dev/api/v1/healthz
```

## Restore from B2 (when local disk is gone)

```bash
# On a fresh VPS with rclone configured:
rclone copy b2:vibecell-backups/daily/ /tmp/restore/ --include "hangar-2026-04-25.sql.gz"

# Then proceed with steps 2–7 above, using /tmp/restore/<file>.sql.gz.
```

## What gets backed up

- All schemas inside the `hangar` database via `pg_dump -U hangar hangar`
- That includes: users, workspaces, projects, sessions, decisions, ideas, ships,
  todos, mcp_audit_log, oauth_clients/auth_codes/tokens/refresh_tokens,
  magic_link_tokens, screenshots metadata, env_fingerprints, secrets vault
  (encrypted at rest with workspace DEK).

## What does NOT get backed up

- Project screenshots in `/srv/hangar/screenshots/` — separate concern. Add
  if/when the screenshot count gets meaningful.
- Server-side static config in `/etc/hangar/hangar.env` — bootstrap-only,
  treat as you'd treat infra IaC. Live in a secret manager (Bitwarden/1Password).
- Container logs — ephemeral by design. Use Sentry for what matters.

## Failure modes & what to do

| Symptom | Likely cause | Action |
|---|---|---|
| `restore-drill.sh` exits 1 | No backups in dir | Check `/var/log/hangar-backup.log` for cron errors |
| `restore-drill.sh` exits 2 | gunzip or psql failed | Backup is corrupt — try the next-newest file. Find why current file is bad. |
| `restore-drill.sh` exits 3 | Schema check returns 0 users | Restore worked but data is empty — check pg_dump didn't fail silently |
| `backup.sh` says "off-site sync ok" but B2 is empty | rclone config wrong | `rclone lsd b2:` to debug. Check key permissions in B2 dashboard. |
| Daily file size drops 10x | Real data loss OR pg_dump failure | Investigate immediately — could be data or backup process |

## Setting up Backblaze B2 (one-time)

1. Sign up at [backblaze.com](https://www.backblaze.com/cloud-storage), free tier = 10 GB
2. Create a private bucket, name it `vibecell-backups`
3. Create an application key with read+write to that bucket only (NOT account-level master key)
4. Add to `/etc/hangar/hangar.env`:
   ```
   BACKUP_B2_KEY_ID=<from B2 dashboard>
   BACKUP_B2_APPLICATION_KEY=<from B2 dashboard>
   BACKUP_B2_BUCKET=vibecell-backups
   ```
5. Install rclone: `apt update && apt install -y rclone`
6. Run `/srv/hangar/ops/backup.sh` once to verify the off-site sync works
7. Confirm the file appears: `rclone lsd b2:vibecell-backups`

Cost at current data size: $0/month (under free tier). At 100k users: ~$0.50/month.
