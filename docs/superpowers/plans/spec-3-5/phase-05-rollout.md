# Phase 5 — Production Rollout

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Deploy Phases 1–4 to production, verify end-to-end with a real Claude Desktop instance, wire up monitoring, and announce. This phase does not introduce new features; it validates the shipped system in the real environment.

**Architecture:** Uses existing VPS deployment pipeline at 89.167.111.89. No new infra needed beyond ENV additions + a Grafana panel. Phase follows the established pattern: SSH → migration → docker compose build/up → smoke tests.

**Prerequisite:** Phases 1–4 complete and green on `main`.

---

## Task 5.1 — Production env + secrets

**Files:**
- Modify: `/etc/hangar/hangar.env` on VPS
- Document: update `docs/ops/ENV.md` or equivalent

- [ ] **Step 1: Generate strong OAUTH_JWT_SECRET**

```bash
# On the VPS, not in the repo
openssl rand -hex 64
# Copy output, update /etc/hangar/hangar.env
```

- [ ] **Step 2: Add to VPS env file**

Add these lines to `/etc/hangar/hangar.env` (SSH to the VPS first):

```dotenv
OAUTH_JWT_SECRET=<generated_hex_from_step_1>
# Other OAuth settings use code defaults (TTLs, limits). Override here only if you need to.
```

- [ ] **Step 3: Document**

Update `docs/ops/ENV.md` (or the equivalent deployment checklist) to include the new secret. Mark as "REQUIRED — generate per-environment with openssl rand -hex 64". Do NOT commit the actual secret value.

- [ ] **Step 4: Commit docs**

```bash
git add docs/ops/ENV.md
git commit -m "docs(ops): document OAUTH_JWT_SECRET requirement for Spec 3.5 rollout"
```

---

## Task 5.2 — Staging deploy + smoke

**Files:** none (operational)

- [ ] **Step 1: Sync to VPS**

```bash
# From laptop
cd C:/Users/ender/OneDrive/Desktop/Hangar
scp -r backend/app/oauth backend/app/mcp backend/app/metrics backend/app/jobs backend/app/api/v1/connections.py backend/app/services/connections.py backend/app/mcp/audit.py root@89.167.111.89:/srv/hangar/backend/app/
scp backend/alembic/versions/0005_oauth.py backend/alembic/versions/0006_mcp_audit_log.py root@89.167.111.89:/srv/hangar/backend/alembic/versions/
scp backend/app/main.py backend/app/core/config.py backend/pyproject.toml backend/uv.lock root@89.167.111.89:/srv/hangar/backend/
scp -r frontend/src/pages/OAuthConsent.vue frontend/src/pages/Connections.vue frontend/src/pages/Dashboard.vue frontend/src/stores/connections.ts frontend/src/api/connections.ts frontend/src/components/connections/ConnectModal.vue frontend/src/router.ts root@89.167.111.89:/srv/hangar/frontend/src/...
scp -r docs/connect root@89.167.111.89:/srv/hangar/docs/
```

(Preferred: simply `git pull` on VPS if the VPS clone tracks main.)

- [ ] **Step 2: Run migrations**

```bash
ssh root@89.167.111.89 "cd /srv/hangar && docker compose --env-file /etc/hangar/hangar.env -f ops/docker-compose.prod.yml run --rm backend alembic upgrade head"
```
Expected output: `0005_oauth` and `0006_mcp_audit_log` applied.

- [ ] **Step 3: Rebuild + redeploy**

```bash
ssh root@89.167.111.89 "cd /srv/hangar && HANGAR_SHA=\$(date +%s) docker compose --env-file /etc/hangar/hangar.env -f ops/docker-compose.prod.yml build backend frontend && docker compose --env-file /etc/hangar/hangar.env -f ops/docker-compose.prod.yml up -d --force-recreate --no-deps backend frontend nginx"
```

- [ ] **Step 4: Smoke — discovery + DCR**

```bash
# From laptop
curl https://vibecell.dev/.well-known/oauth-authorization-server | jq
curl https://vibecell.dev/.well-known/oauth-protected-resource | jq
curl -X POST https://vibecell.dev/oauth/register \
  -H "Content-Type: application/json" \
  -d '{"client_name":"rollout-test","redirect_uris":["http://127.0.0.1:65432/cb"]}'
```
Expected: Discovery JSON matches spec; register returns `client_id` starting with `dyn_`.

- [ ] **Step 5: Smoke — /metrics**

```bash
curl https://vibecell.dev/metrics | head -50
```
Expected: Prometheus-format output with `oauth_tokens_issued_total`, `mcp_tool_calls_total`, etc.

- [ ] **Step 6: Manual OAuth flow with curl**

Full script:

```bash
# scripts/rollout-verify.sh — keep in repo for re-run
set -euo pipefail
BASE=https://vibecell.dev

REG=$(curl -s -X POST "$BASE/oauth/register" \
  -H "Content-Type: application/json" \
  -d '{"client_name":"rollout-verify","redirect_uris":["http://127.0.0.1:65432/cb"]}')
CID=$(echo "$REG" | jq -r .client_id)
echo "Registered: $CID"

VERIFIER=$(openssl rand -hex 32 | head -c 43)
CHALLENGE=$(echo -n "$VERIFIER" | openssl dgst -sha256 -binary | openssl base64 | tr -d '=' | tr '/+' '_-')

AUTH_URL="$BASE/oauth/authorize?response_type=code&client_id=$CID&redirect_uri=http%3A%2F%2F127.0.0.1%3A65432%2Fcb&code_challenge=$CHALLENGE&code_challenge_method=S256&state=rollout&scope=vibecell:tools"
echo "Open in browser, sign in, Allow:"
echo "$AUTH_URL"
read -p "Paste the 'code' query param from the redirect: " CODE

TOK=$(curl -s -X POST "$BASE/oauth/token" \
  -d "grant_type=authorization_code" \
  -d "code=$CODE" \
  -d "redirect_uri=http://127.0.0.1:65432/cb" \
  -d "client_id=$CID" \
  -d "code_verifier=$VERIFIER")
echo "$TOK" | jq
ACCESS=$(echo "$TOK" | jq -r .access_token)

echo "Calling MCP initialize + tools/list + ping..."
curl -s -X POST "$BASE/mcp" \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | jq
curl -s -X POST "$BASE/mcp" \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | jq '.result.tools | length'
curl -s -X POST "$BASE/mcp" \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"vibecell.ping","arguments":{}}}' | jq
```

- [ ] **Step 7: Commit the verify script**

```bash
git add scripts/rollout-verify.sh
git commit -m "ops: Spec 3.5 end-to-end rollout verification script"
```

---

## Task 5.3 — Real Claude Desktop verification

**Files:** none (operational)

- [ ] **Step 1: On macOS Claude Desktop**

1. Open Claude Desktop → Settings → Connectors → "Add Remote Server"
2. URL: `https://vibecell.dev`
3. Click "Add"
4. Browser opens vibecell.dev/oauth/authorize. Sign in (magic link) if needed. Pick workspace. Click "Allow & Connect".
5. Desktop shows "Connected — 17 tools available".
6. Open a new chat: ask Claude "What projects do I have?" — Claude calls `vibecell.list`, responds with live data.

Document any UX friction (e.g. text too small, workspace name not visible, loading spinner stuck). File as Phase 5.5 follow-ups.

- [ ] **Step 2: On Windows Claude Desktop**

Repeat step 1 on Windows. Capture differences (keychain vs credential-manager token storage, deep-link behavior).

- [ ] **Step 3: Revoke flow test**

1. Go to `https://vibecell.dev/settings/connections` in browser
2. Click "Revoke" on the Claude Desktop entry
3. Back in Claude Desktop, ask "what projects do I have?" — Claude should see 401, Desktop should re-prompt OAuth (or surface "disconnected").

- [ ] **Step 4: Record findings**

Create a brief dev-log note at `docs/superpowers/notes/2026-04-2X-spec-3-5-rollout.md` documenting: what worked, what didn't, which edge cases surprised, any bug-fix commits pushed during verification. No formal spec update needed unless a real defect.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/notes/2026-04-2X-spec-3-5-rollout.md
git commit -m "docs(rollout): Spec 3.5 manual verification notes"
```

---

## Task 5.4 — Grafana dashboard

**Files:**
- Create: `ops/grafana/dashboards/spec-3-5-remote-mcp.json`

- [ ] **Step 1: Build dashboard in Grafana UI**

Panels (6 total):

1. **OAuth Tokens Issued (rate/min)** — `rate(oauth_tokens_issued_total[5m])` — line chart.
2. **OAuth Authorize Outcomes** — `sum by (outcome) (rate(oauth_authorize_redirects_total[5m]))` — stacked area, `granted/denied/error`.
3. **MCP Tool Calls (top 10 by rate)** — `topk(10, sum by (tool_name) (rate(mcp_tool_calls_total[5m])))` — bar gauge.
4. **MCP Tool Error Rate** — `sum by (tool_name) (rate(mcp_tool_calls_total{status="error"}[5m]))` — line.
5. **MCP Auth Failures by Reason** — `sum by (reason) (rate(mcp_auth_failures_total[5m]))` — line.
6. **Active MCP Connections** — `mcp_active_connections` — single stat.

- [ ] **Step 2: Export + commit**

In Grafana, Dashboard → Settings → JSON Model → copy → save to file.

```bash
git add ops/grafana/dashboards/spec-3-5-remote-mcp.json
git commit -m "ops(grafana): Spec 3.5 dashboard — OAuth issuance + MCP tool traffic + auth failures"
```

- [ ] **Step 3: Auto-import on Grafana startup**

Ensure `ops/docker-compose.prod.yml` mounts `ops/grafana/dashboards/` into Grafana's provisioning directory; if not, add:

```yaml
grafana:
  volumes:
    - ./ops/grafana/dashboards:/etc/grafana/provisioning/dashboards
```

Commit if changes.

---

## Task 5.5 — Announcement

**Files:**
- Create: changelog entry
- Create: blog post or tweet draft (optional)

- [ ] **Step 1: Cut release**

Run `hangar.exe ship` locally against the vibecell project (dogfooding the CLI):

```bash
hangar ship --version v0.4.0-spec-3-5 --summary "Remote MCP server on vibecell.dev — zero-install Claude Desktop / Cursor / Zed integration" --changelog "$(cat <<'EOF'
## v0.4.0 — Remote MCP + OAuth 2.1

### Added
- `https://vibecell.dev/mcp` — spec-compliant MCP Streamable HTTP endpoint
- Full OAuth 2.1 with Dynamic Client Registration (RFC 7591)
- `.well-known/oauth-authorization-server` + `.well-known/oauth-protected-resource` discovery
- Branded consent screen with workspace picker
- `/settings/connections` — unified OAuth + CLI device list with one-click revoke
- `ConnectModal` on dashboard with multi-client tabs (Claude Desktop, Code, Cursor, Zed, Windsurf)
- 17 remote tools (all except `vibecell.run`, which stays CLI-only)
- Prometheus metrics + Grafana dashboard
- Daily cron: orphan DCR client cleanup + 30-day audit log retention

### Rollout
- Migrations `0005_oauth` + `0006_mcp_audit_log` deployed to prod
- Real Claude Desktop verified on macOS + Windows
- Monitoring active at `/metrics` + Grafana
EOF
)"
```

- [ ] **Step 2: Announce (optional — user decides)**

Tweet draft:

> Shipped: vibecell.dev now speaks MCP over OAuth 2.1. Claude Desktop, Cursor, Zed → point at vibecell.dev → consent → done. 17 tools, workspace-scoped, one-click revoke. Zero-install.

Blog post outline: saved to `docs/blog/drafts/2026-04-2X-remote-mcp.md` for later polish.

- [ ] **Step 3: Git tag + push**

```bash
git tag v0.4.0-spec-3-5
git push origin main --tags
```

---

## Task 5.6 — 2-week monitoring window

**Files:**
- Tracking doc: `docs/superpowers/notes/spec-3-5-monitoring-log.md`

- [ ] **Daily for 14 days, record:**

- Tokens issued per day
- Unique clients connected
- Tool-call volume + top-5 tools
- Error rate by tool
- Auth failure count + most common reason
- Revocations (for trust tracking)
- Any Sentry exceptions from `app.oauth.*` or `app.mcp.*`

- [ ] **At end of 14 days:**

If error rate < 1% of tool calls and no CRITICAL Sentry issues: mark Spec 3.5 as **stable** in `HANGAR.md` §13 roadmap. Commit:

```bash
git commit -m "docs(status): Spec 3.5 marked stable after 14-day monitoring window"
```

If issues found: open Spec 3.5.1 to address, follow normal brainstorm → plan → implement cycle.

---

## End of Phase 5 — Checklist

- [ ] Prod `.env` has `OAUTH_JWT_SECRET` set
- [ ] Migrations 0005 + 0006 applied to prod DB
- [ ] Prod `/metrics` returns populated counters
- [ ] `rollout-verify.sh` succeeds against prod
- [ ] Real Claude Desktop connects + calls tools on macOS and Windows
- [ ] Revoke flow verified (tool call fails after revoke)
- [ ] Grafana dashboard imported + visible
- [ ] Release tag `v0.4.0-spec-3-5` pushed
- [ ] 14-day monitoring log started

---

## End of Spec 3.5 — Done

Vibecell is now a zero-install MCP provider. Any MCP client can connect in under 60 seconds without downloading anything.
