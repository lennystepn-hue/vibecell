#!/usr/bin/env bash
#
# Post-deploy smoke test: assert what the deployment actually serves.
#
# Usage:
#   ./ops/smoke.sh                       # against https://vibecell.dev
#   ./ops/smoke.sh http://localhost:8080 # against a local stack
#
# Why this exists: three bugs reached production on one afternoon, all green
# in CI, all visible within seconds of touching the real URL.
#
#   * /i/<code> wasn't routed in nginx, so the SPA answered with text/html
#     and `curl … | sh` piped an HTML document into a shell
#   * /api/v1/onboarding/stream fell into the generic /api/ block, so the
#     "live" log was buffered and cut off after 60s
#   * /releases/ was never wired to anything, so a 200 + index.html got
#     saved as a .zip and surfaced as "central directory not found"
#
# All three live in the gap between "the application is correct" and "the
# deployment serves it". Backend tests call FastAPI directly and never
# traverse nginx; frontend tests never leave jsdom. Nothing covered this
# layer, so every assertion below is one that would have caught a real
# failure the same day it shipped.
#
# Exit code is the number of failed checks, so CI and deploy.sh can gate.

set -uo pipefail

BASE="${1:-https://vibecell.dev}"
BASE="${BASE%/}"
FAILED=0
PASSED=0

red()   { printf '\033[31m%s\033[0m' "$1"; }
green() { printf '\033[32m%s\033[0m' "$1"; }

pass() { PASSED=$((PASSED + 1)); printf '  %s %s\n' "$(green ✓)" "$1"; }
fail() {
  FAILED=$((FAILED + 1))
  printf '  %s %s\n' "$(red ✗)" "$1"
  [ -n "${2:-}" ] && printf '      %s\n' "$2"
  return 0
}

# --- helpers ---------------------------------------------------------------

status_of() { curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$1"; }
ctype_of()  { curl -s -o /dev/null -w '%{content_type}' --max-time 20 "$1"; }

expect_status() { # url expected label
  local got; got="$(status_of "$1")"
  if [ "$got" = "$2" ]; then pass "$3"; else fail "$3" "expected HTTP $2, got $got"; fi
}

echo
echo "smoke: $BASE"
echo

# --- 1. the app is up ------------------------------------------------------

echo "app"
expect_status "$BASE/api/v1/healthz" 200 "healthz responds"
expect_status "$BASE/" 200 "landing renders"
expect_status "$BASE/pricing" 200 "pricing renders"
expect_status "$BASE/status" 200 "status page renders"

# --- 2. the one-line installer ---------------------------------------------
#
# The whole setup flow hangs off these three, and every one of them failed
# in production while the test suite stayed green.

echo
echo "install path"

# /i/<code> must reach the backend. A dead code still returns 200 with a
# script that explains itself — a 404 body piped into `sh` is a parse error,
# not a message. The failure mode we are guarding is nginx handing this to
# the SPA, which answers 200 text/html and looks fine to a status check.
I_BODY="$(curl -s --max-time 20 "$BASE/i/SMOKETEST")"
I_CTYPE="$(ctype_of "$BASE/i/SMOKETEST")"
if [[ "$I_CTYPE" == *"text/html"* ]]; then
  fail "/i/<code> is served by the backend" "content-type is $I_CTYPE — the SPA is answering"
elif [[ "$I_BODY" == "#!"* || "$I_BODY" == "Write-Error"* ]]; then
  pass "/i/<code> is served by the backend"
else
  fail "/i/<code> is served by the backend" "body does not look like a script: ${I_BODY:0:60}"
fi

# The binaries actually download. Redirect to GitHub Releases, then a real
# archive on the other end — not an HTML page with a .zip filename.
REL_URL="$BASE/releases/hangar-x86_64-pc-windows-msvc.zip"
REDIR="$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 20 "$REL_URL")"
if [[ "$REDIR" == *"github.com"*"/releases/"* ]]; then
  pass "/releases/ redirects to GitHub"
else
  fail "/releases/ redirects to GitHub" "redirect_url was '${REDIR:-<none>}'"
fi

MAGIC="$(curl -sL --max-time 60 "$REL_URL" | head -c 2)"
if [ "$MAGIC" = "PK" ]; then
  pass "windows archive is a real zip"
else
  fail "windows archive is a real zip" "first bytes were '$MAGIC', not 'PK' — probably an HTML error page"
fi

# install.sh must be LF. A CRLF shebang breaks `curl … | sh` on macOS and
# Linux, and it shipped that way once because a Windows checkout converted it.
if curl -s --max-time 20 "$BASE/install.sh" | grep -q $'\r'; then
  fail "install.sh has unix line endings" "found CR — curl | sh will break on macOS/Linux"
else
  pass "install.sh has unix line endings"
fi

# --- 3. onboarding endpoints are wired and guarded -------------------------

echo
echo "onboarding"
expect_status "$BASE/api/v1/onboarding/stream" 401 "stream requires auth"
expect_status "$BASE/api/v1/onboarding/code" 405 "code endpoint exists (GET not allowed)"

# A dead code must 404 rather than 422 or 500 — the installer's error message
# depends on telling "expired" apart from "broken".
REDEEM="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
  -X POST "$BASE/api/v1/onboarding/redeem" \
  -H 'content-type: application/json' \
  --data-binary '{"code":"SMOKETEST"}')"
if [ "$REDEEM" = "404" ]; then
  pass "unknown pairing code is rejected with 404"
else
  fail "unknown pairing code is rejected with 404" "got HTTP $REDEEM"
fi

# --- 4. MCP is reachable ---------------------------------------------------

echo
echo "mcp"
MCP_CTYPE="$(ctype_of "$BASE/mcp")"
if [[ "$MCP_CTYPE" == *"text/html"* ]]; then
  fail "/mcp reaches the backend" "content-type is $MCP_CTYPE — the SPA is answering"
else
  pass "/mcp reaches the backend"
fi

# --- summary ---------------------------------------------------------------

echo
if [ "$FAILED" -eq 0 ]; then
  printf '%s %d checks passed\n\n' "$(green 'smoke ok —')" "$PASSED"
else
  printf '%s %d of %d checks failed\n\n' "$(red 'smoke FAILED —')" "$FAILED" "$((PASSED + FAILED))"
fi
exit "$FAILED"
