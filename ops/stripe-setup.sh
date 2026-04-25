#!/bin/bash
# Vibecell — one-shot Stripe setup.
#
# Creates Product + Price + Webhook in your Stripe account, prints the env
# vars to paste into /etc/hangar/hangar.env, updates the prod DB row.
#
# Run this locally with the Stripe secret in your shell — it never touches
# Claude / Vibecell logs:
#
#   STRIPE_SECRET_KEY=sk_live_xxx bash ops/stripe-setup.sh
#
# Idempotent. Safe to re-run. Looks up an existing "Vibecell Pro" Product
# before creating, picks the same Price if its amount + interval match.
#
# Requirements:
#   - bash, curl, jq
#   - SSH access to root@89.167.111.89 (so we can update the DB)
#   - STRIPE_SECRET_KEY env var set (export it before running)

set -euo pipefail

if [ -z "${STRIPE_SECRET_KEY:-}" ]; then
  echo "FATAL: STRIPE_SECRET_KEY not set."
  echo "Run: STRIPE_SECRET_KEY=sk_live_xxx bash $0"
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "FATAL: jq is required (apt install jq / brew install jq)."
  exit 1
fi

API="https://api.stripe.com/v1"
AUTH=(-u "$STRIPE_SECRET_KEY:")

# ---------- 1. Product ------------------------------------------------------
echo "==> Looking up existing 'Vibecell Pro' product..."
PRODUCTS=$(curl -sf "${AUTH[@]}" "$API/products?limit=100&active=true")
PRODUCT_ID=$(echo "$PRODUCTS" | jq -r '.data[] | select(.name=="Vibecell Pro") | .id' | head -n1)

if [ -z "$PRODUCT_ID" ] || [ "$PRODUCT_ID" = "null" ]; then
  echo "==> No existing product — creating 'Vibecell Pro'..."
  PRODUCT_ID=$(curl -sf "${AUTH[@]}" "$API/products" \
    -d "name=Vibecell Pro" \
    -d "description=Project memory for Claude & Cursor — unlimited projects, AI enrichment, MCP server access." \
    -d "metadata[plan_slug]=pro" | jq -r '.id')
  echo "    created: $PRODUCT_ID"
else
  echo "    found: $PRODUCT_ID"
fi

# ---------- 2. Price --------------------------------------------------------
echo "==> Looking up existing recurring price (899 cents EUR / month)..."
PRICES=$(curl -sf "${AUTH[@]}" "$API/prices?product=$PRODUCT_ID&active=true&limit=100")
PRICE_ID=$(echo "$PRICES" | jq -r '
  .data[]
  | select(.unit_amount==899 and .currency=="eur" and .recurring.interval=="month")
  | .id
' | head -n1)

if [ -z "$PRICE_ID" ] || [ "$PRICE_ID" = "null" ]; then
  echo "==> Creating €8.99/month recurring price..."
  PRICE_ID=$(curl -sf "${AUTH[@]}" "$API/prices" \
    -d "product=$PRODUCT_ID" \
    -d "unit_amount=899" \
    -d "currency=eur" \
    -d "recurring[interval]=month" \
    -d "tax_behavior=exclusive" \
    -d "nickname=Vibecell Pro Monthly" | jq -r '.id')
  echo "    created: $PRICE_ID"
else
  echo "    found:   $PRICE_ID"
fi

# ---------- 3. Webhook ------------------------------------------------------
echo "==> Looking up existing webhook for https://vibecell.dev/api/v1/billing/webhook ..."
HOOKS=$(curl -sf "${AUTH[@]}" "$API/webhook_endpoints?limit=100")
HOOK_ID=$(echo "$HOOKS" | jq -r '
  .data[]
  | select(.url=="https://vibecell.dev/api/v1/billing/webhook")
  | .id
' | head -n1)

EVENTS=(
  "customer.subscription.created"
  "customer.subscription.updated"
  "customer.subscription.deleted"
  "invoice.payment_failed"
  "invoice.payment_succeeded"
)

EVENT_ARGS=()
for e in "${EVENTS[@]}"; do EVENT_ARGS+=(-d "enabled_events[]=$e"); done

WEBHOOK_SECRET=""
if [ -z "$HOOK_ID" ] || [ "$HOOK_ID" = "null" ]; then
  echo "==> Creating webhook endpoint..."
  HOOK_RESPONSE=$(curl -sf "${AUTH[@]}" "$API/webhook_endpoints" \
    -d "url=https://vibecell.dev/api/v1/billing/webhook" \
    "${EVENT_ARGS[@]}")
  HOOK_ID=$(echo "$HOOK_RESPONSE" | jq -r '.id')
  WEBHOOK_SECRET=$(echo "$HOOK_RESPONSE" | jq -r '.secret')
  echo "    created: $HOOK_ID"
else
  echo "    found:   $HOOK_ID (existing — secret cannot be re-fetched)"
  echo "    NOTE: if you don't have HANGAR_STRIPE_WEBHOOK_SECRET set already,"
  echo "          delete the existing endpoint at"
  echo "          https://dashboard.stripe.com/webhooks/$HOOK_ID and re-run."
fi

# ---------- 4. Update prod DB ----------------------------------------------
echo
echo "==> Stamping plans.stripe_price_id on the prod DB..."
ssh -o StrictHostKeyChecking=no root@89.167.111.89 \
  "docker exec hangar-postgres-1 psql -U hangar -d hangar -c \"UPDATE plans SET stripe_price_id='$PRICE_ID' WHERE slug='pro'\""

# ---------- 5. Print env block ---------------------------------------------
echo
echo "==> ALL DONE. Add the following to /etc/hangar/hangar.env on the server,"
echo "    then run \`docker compose restart backend\`:"
echo
echo "------------------------------------------------------------"
echo "HANGAR_STRIPE_SECRET_KEY=$STRIPE_SECRET_KEY"
if [ -n "$WEBHOOK_SECRET" ]; then
  echo "HANGAR_STRIPE_WEBHOOK_SECRET=$WEBHOOK_SECRET"
else
  echo "# HANGAR_STRIPE_WEBHOOK_SECRET=<re-fetch from Stripe Dashboard or recreate the webhook>"
fi
echo "HANGAR_STRIPE_PRO_PRICE_ID=$PRICE_ID"
echo "------------------------------------------------------------"
echo
echo "Stripe Tax: enable manually at https://dashboard.stripe.com/tax/settings"
echo "(otherwise EU VAT won't be collected)."
