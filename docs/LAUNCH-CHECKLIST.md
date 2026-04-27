# Vibecell Launch Checklist · Spec-6 Sprint C

Last verified: **2026-04-27** · Build **`b51ffb8`**

This is the runbook for the v1.0.0 launch. Each section has a green / amber /
red verdict + the exact command used to verify, so re-running the check after
any deploy is two seconds of copy-paste.

---

## 1 · Externally reachable surfaces

| Surface | URL | Expected | Verified |
|--|--|--|--|
| Landing | https://vibecell.dev/ | 200 + AnonLanding | ✅ green |
| Pricing | https://vibecell.dev/pricing | 200 + monthly/annual cards | ✅ green |
| Status | https://vibecell.dev/status | 200 + all components ok | ✅ green |
| Legal | https://vibecell.dev/legal | 200 + Imprint/Privacy/Terms | ✅ green |
| Healthz | https://vibecell.dev/api/v1/healthz | `{"ok":true,…}` | ✅ green |
| Status API | https://vibecell.dev/api/v1/status | `{"overall":"ok",…}` | ✅ green |
| MCP | https://vibecell.dev/mcp | 401 anon → 200 with bearer | ✅ green |
| Billing webhook | https://vibecell.dev/api/v1/billing/webhook | 400 on garbage (sig check) | ✅ green |

```bash
curl -s https://vibecell.dev/api/v1/healthz
curl -s https://vibecell.dev/api/v1/status | jq
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
    https://vibecell.dev/api/v1/billing/webhook -d '{}'
# expect: 400  (signature rejected — endpoint is wired)
```

---

## 2 · DNS

```
vibecell.dev          A     89.167.111.89   (Cloudflare proxied)
www.vibecell.dev      A     89.167.111.89   (Cloudflare proxied)
status.vibecell.dev   CNAME vibecell.dev    (Cloudflare proxied) ← TODO
```

**status.vibecell.dev not yet pointed.** Add the CNAME in Cloudflare's DNS panel
(Proxied = on so the edge cert covers it automatically). Once DNS propagates,
run the cert-expand step in §3 to add the SAN to the origin cert.

---

## 3 · TLS / SSL

Edge cert: managed by Cloudflare (Universal SSL · ECDSA · TLS 1.3). Origin cert:
Let's Encrypt via certbot HTTP-01, currently covers `vibecell.dev` and
`www.vibecell.dev`. Auto-renewal via the `certbot` cron in agentready stack.

| Check | Result |
|--|--|
| HSTS preload header | `max-age=63072000; includeSubDomains; preload` ✅ |
| Frame-options | `DENY` ✅ |
| Content-Security-Policy | restrictive default-src 'self' ✅ |
| Permissions-Policy | camera/mic/geo/cohort all denied ✅ |
| Referrer-Policy | `strict-origin-when-cross-origin` ✅ |
| TLS verify | OK (curl `ssl_verify_result=0`) ✅ |

```bash
curl -sI https://vibecell.dev/ | grep -iE \
    "strict-transport|x-frame|content-security|permissions-policy|referrer"
```

**Add status.vibecell.dev SAN once DNS resolves:**

```bash
ssh root@89.167.111.89 \
    "docker run --rm --network host \
       -v agentready_certbot-conf:/etc/letsencrypt \
       -v agentready_certbot-www:/var/www/certbot \
       certbot/certbot certonly --webroot \
       --webroot-path /var/www/certbot \
       --cert-name vibecell.dev --expand \
       -d vibecell.dev -d www.vibecell.dev -d status.vibecell.dev \
       --non-interactive --agree-tos -m lennystepn@gmail.com"
ssh root@89.167.111.89 "docker exec agentready-nginx-1 nginx -s reload"
```

---

## 4 · Stripe

| Item | Status |
|--|--|
| `HANGAR_STRIPE_SECRET_KEY` | ✅ set (live key) |
| `HANGAR_STRIPE_WEBHOOK_SECRET` | ✅ set |
| `HANGAR_STRIPE_PRO_PRICE_ID` | ✅ set (€8.99 monthly) |
| `HANGAR_STRIPE_PRO_ANNUAL_PRICE_ID` | ✅ set (€99.99 annual) |
| `HANGAR_STRIPE_LAUNCH_COUPON_ID` | ✅ set (LAUNCH69 · €30 off · 100 redemptions) |
| Webhook endpoint | https://vibecell.dev/api/v1/billing/webhook ✅ reachable, signature-validated |
| Customer portal | live ✅ |

**End-to-end smoke** (do this after first signup of the launch day):

1. New incognito → sign up → check email → magic link → land on `/welcome`
2. Step 1: create a project → step 2: skip pairing → step 3 done
3. `/settings/billing` → "Upgrade — annual" → use real card or 4242…
4. Confirm Stripe dashboard shows the customer + sub
5. Confirm `subscriptions` table has status `active` for that user
6. Cancel via portal → confirm `cancel_at_period_end = true` in DB
7. (post period_end) confirm middleware returns 402 on writes

---

## 5 · Observability

| Source | Status |
|--|--|
| `/api/v1/healthz` | ✅ live |
| `/api/v1/status` | ✅ live, polled by /status SPA |
| Prometheus `/metrics` | ✅ live (gated to internal IPs) |
| Backend logs | docker logs hangar-backend-1 |
| Sentry (backend) | ⚠️ **not configured** — set `SENTRY_DSN_BACKEND` to enable |
| Sentry (frontend) | ⚠️ **not configured** — set `SENTRY_DSN_FRONTEND` at build time |

**Wire up Sentry (post-launch nice-to-have):**

```bash
# Backend — add to /etc/hangar/hangar.env
echo "SENTRY_DSN_BACKEND=https://...@...ingest.sentry.io/..." \
    | ssh root@89.167.111.89 "tee -a /etc/hangar/hangar.env"
ssh root@89.167.111.89 "docker restart hangar-backend-1"
# Verify with a test event:
ssh root@89.167.111.89 \
    "docker exec hangar-backend-1 python -c \
     'import sentry_sdk; sentry_sdk.capture_message(\"vibecell launch test\")'"
# Check Sentry → should appear in <1 min
```

---

## 6 · Database & migrations

```bash
ssh root@89.167.111.89 \
    "docker exec hangar-backend-1 alembic current"
# expect: 0020 (head)
```

Migrations through 0020 applied · sessions de-duped (104 rows removed) ·
subscriptions backfilled · billing tables seeded with `pro` plan.

---

## 7 · Backups

| Schedule | Location |
|--|--|
| Daily pg_dump | `/srv/hangar/backups/` (root@89.167.111.89) via `ops/backup.sh` |
| Restore drill | `ops/restore-drill.sh` — manual, runs ⩾ once/quarter |

Last drill: Sprint A4 (verified roundtrip). Repeat ≥ Q3-2026.

---

## 8 · Launch-day rollout sequence

1. Run §1 verification commands → all ✅
2. Add `status.vibecell.dev` CNAME in Cloudflare → wait propagation (≤ 5 min)
3. Run cert-expand command (§3) → reload nginx → `curl -I https://status.vibecell.dev/` returns 200 / redirects to /status
4. Tag `v0.6.C-launch` (this commit) in git
5. Post launch announcements (see `LAUNCH-POSTS.md`)
6. Watch `docker logs -f hangar-backend-1` for first 30 min
7. Confirm first signup on the dashboard, watch /api/v1/status for any degradation
8. After 24h of stability + first paid signup, tag `v1.0.0`
