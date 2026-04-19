# Production deploy — Vibecell

Staging + first production instance: `89.167.111.89` (Hetzner Helsinki, 4 GB).

## Prerequisites on the server

- Docker + Docker Compose v2 (already installed).
- `/etc/hangar/hangar.env` with production secrets.
- DNS: point `vibecell.dev` (and `www.vibecell.dev`) at the server's IP.

### Server environment file

Create `/etc/hangar/hangar.env` (root:root, chmod 600):

```ini
HANGAR_MASTER_KEY=<generate via: python -c "import secrets; print(secrets.token_urlsafe(32))">
HANGAR_DATABASE_URL=postgresql+asyncpg://hangar:<POSTGRES_PASSWORD>@postgres:5432/hangar
HANGAR_REDIS_URL=redis://redis:6379/0
HANGAR_RESEND_API_KEY=re_...
HANGAR_GITHUB_CLIENT_ID=...
HANGAR_GITHUB_CLIENT_SECRET=...
HANGAR_BASE_URL=https://vibecell.dev
HANGAR_COOKIE_DOMAIN=vibecell.dev
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

## Expose vibecell.dev

Two options:

### Option 1: Route through existing `agentready-nginx` (current setup)

The server already runs `agentready-nginx` on ports 80/443. The canonical
server block lives in-repo at `ops/nginx/vibecell.dev.conf`, with a
transitional HTTP-only version at `ops/nginx/vibecell.dev.http-only.conf`
used during cert bootstrap. The outer nginx proxies to `hangar-nginx-1`
via the host gateway `http://172.17.0.1:8080` (docker0 bridge — no
compose-file change needed on the agentready side).

**First-time cert issuance** (once DNS A record points vibecell.dev at
89.167.111.89):

```bash
scp ops/nginx/vibecell.dev.http-only.conf \
    root@89.167.111.89:/tmp/vibecell-http.conf
ssh root@89.167.111.89 'docker cp /tmp/vibecell-http.conf \
  agentready-nginx-1:/etc/nginx/conf.d/vibecell.conf && \
  docker exec agentready-nginx-1 nginx -s reload'

scp ops/issue-cert.sh root@89.167.111.89:/tmp/issue-cert.sh
ssh root@89.167.111.89 'chmod +x /tmp/issue-cert.sh && /tmp/issue-cert.sh'
```

The script does a DNS gate + HTTP-01 self-check, then runs certbot
webroot, then swaps in `vibecell.dev.conf` and reloads nginx.

**Renewal** is handled by the existing `agentready-certbot-1` container
(internal 12h renew loop). A crontab entry reloads agentready-nginx-1
nightly at 03:15 UTC so freshly renewed certs get picked up.

### Option 2: Cloudflare proxy

Point `vibecell.dev` A record at 89.167.111.89, orange-cloud on. Cloudflare
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
docker compose --env-file /etc/hangar/hangar.env \
  -f /srv/hangar/ops/docker-compose.prod.yml exec -T postgres \
  psql -U hangar -d hangar < /srv/hangar/backups/daily/hangar-2026-04-20.sql.gz.decompressed
```

Or in-place:

```bash
gunzip -c /srv/hangar/backups/daily/hangar-YYYY-MM-DD.sql.gz \
  | docker compose --env-file /etc/hangar/hangar.env \
  -f /srv/hangar/ops/docker-compose.prod.yml exec -T postgres \
    psql -U hangar -d hangar
```

## Uptime monitoring

Point an external pinger (UptimeRobot free tier works) at:

- `https://vibecell.dev/api/v1/healthz` — must return `{"ok": true}` with status 200.
- Alert threshold: down for > 2 checks in a row (10 min).

## Rollback

`deploy.sh` auto-rolls back on health-check fail. Manual rollback:

```bash
ssh root@89.167.111.89 "cd /srv/hangar && HANGAR_SHA=<prev-sha> docker compose --env-file /etc/hangar/hangar.env -f ops/docker-compose.prod.yml up -d backend frontend nginx"
```

## Secret rotation

1. Edit `/etc/hangar/hangar.env` on the server (root:root, mode 600).
2. `docker compose --env-file /etc/hangar/hangar.env -f ops/docker-compose.prod.yml restart backend`.
3. Verify via `/api/v1/healthz`.
