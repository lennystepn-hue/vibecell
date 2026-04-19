#!/usr/bin/env bash
# Issue (or renew) the vibecell.dev TLS cert via certbot webroot challenge.
#
# Run on the staging/prod VPS (89.167.111.89) AFTER:
#   1. DNS: `dig +short vibecell.dev` returns 89.167.111.89
#   2. ops/nginx/vibecell.dev.http-only.conf is loaded in agentready-nginx-1
#      (so /.well-known/acme-challenge/ is reachable over HTTP)
#
# After the cert lands, swap the HTTP-only config for the full
# vibecell.dev.conf (HTTP→HTTPS redirect + 443 block).
#
# Idempotent: certbot will no-op if the cert already exists and isn't near
# expiry.

set -euo pipefail

EMAIL="${CERTBOT_EMAIL:-lennystepn@gmail.com}"
DOMAINS=(-d vibecell.dev -d www.vibecell.dev)

# DNS gate — abort clearly if DNS isn't pointing here yet.
EXPECTED_IP="89.167.111.89"
RESOLVED="$(dig +short vibecell.dev @8.8.8.8 | tail -1)"
if [[ "$RESOLVED" != "$EXPECTED_IP" ]]; then
  echo "ABORT: vibecell.dev resolves to '$RESOLVED', expected '$EXPECTED_IP'." >&2
  echo "       Update your DNS A record and wait for propagation first." >&2
  exit 2
fi

# Ensure the HTTP-only config is loaded so the challenge path is reachable.
if ! docker exec agentready-nginx-1 test -f /etc/nginx/conf.d/vibecell.conf; then
  echo "ABORT: /etc/nginx/conf.d/vibecell.conf not present in agentready-nginx-1." >&2
  echo "       Copy ops/nginx/vibecell.dev.http-only.conf into the container first." >&2
  exit 3
fi

# Self-check the challenge path before burning a Let's Encrypt issuance.
TOKEN="$(openssl rand -hex 16)"
docker exec agentready-nginx-1 sh -c "mkdir -p /var/www/certbot/.well-known/acme-challenge && echo $TOKEN > /var/www/certbot/.well-known/acme-challenge/$TOKEN"
CHK="$(curl -fsSL "http://vibecell.dev/.well-known/acme-challenge/$TOKEN" || true)"
docker exec agentready-nginx-1 rm -f "/var/www/certbot/.well-known/acme-challenge/$TOKEN"
if [[ "$CHK" != "$TOKEN" ]]; then
  echo "ABORT: HTTP-01 self-check failed." >&2
  echo "       curl got: '$CHK' (expected '$TOKEN')." >&2
  exit 4
fi
echo "ok HTTP-01 self-check passed"

# Issue the cert.
docker run --rm \
  -v agentready_certbot-conf:/etc/letsencrypt \
  -v agentready_certbot-www:/var/www/certbot \
  certbot/certbot certonly --webroot \
    -w /var/www/certbot \
    "${DOMAINS[@]}" \
    --email "$EMAIL" \
    --agree-tos --non-interactive \
    --key-type ecdsa

# Swap in the full HTTPS config + reload.
docker cp /srv/hangar/ops/nginx/vibecell.dev.conf agentready-nginx-1:/etc/nginx/conf.d/vibecell.conf
docker exec agentready-nginx-1 nginx -t
docker exec agentready-nginx-1 nginx -s reload
echo "ok cert issued + HTTPS config live"
