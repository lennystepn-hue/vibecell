"""Vibecell — server-side Stripe setup (stdlib-only).

Runs ON the production VPS. Reads HANGAR_STRIPE_SECRET_KEY from the
process env. Never echoes the secret. Idempotent.

What it does, in order:
  1. Look up or create Product "Vibecell Pro"
  2. Look up or create the recurring €8.99/month Price
  3. Look up or create the Webhook endpoint
  4. UPDATE plans.stripe_price_id in the prod DB
  5. Append HANGAR_STRIPE_PRO_PRICE_ID + HANGAR_STRIPE_WEBHOOK_SECRET
     (when first generated) to /etc/hangar/hangar.env if missing
  6. Print a one-line summary; never the secret
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


STRIPE_API = "https://api.stripe.com/v1"
WEBHOOK_URL = "https://vibecell.dev/api/v1/billing/webhook"
PRODUCT_NAME = "Vibecell Pro"
PRICE_AMOUNT_CENTS = 899  # monthly
PRICE_ANNUAL_CENTS = 9999  # standard annual (save ~€7 vs 12×monthly)
PRICE_CURRENCY = "eur"
LAUNCH_COUPON_ID = "LAUNCH69"
LAUNCH_COUPON_AMOUNT_OFF = 3000  # €30 off → first-year effective €69.99
LAUNCH_COUPON_MAX = 100  # only first 100 redemptions
ENV_FILE = "/etc/hangar/hangar.env"
DOCKER_PG_CONTAINER = "hangar-postgres-1"
WEBHOOK_EVENTS = [
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
    "invoice.payment_succeeded",
]


def _stripe(method: str, path: str, *, not_found_ok: bool = False, **form: Any) -> dict[str, Any] | None:
    key = os.environ.get("HANGAR_STRIPE_SECRET_KEY", "")
    if not key:
        sys.stderr.write(
            "FATAL: HANGAR_STRIPE_SECRET_KEY not set in env. "
            "Add it to /etc/hangar/hangar.env first.\n"
        )
        sys.exit(2)

    encoded: list[tuple[str, str]] = []
    for k, v in form.items():
        if isinstance(v, list):
            for item in v:
                encoded.append((f"{k}[]", str(item)))
        elif isinstance(v, dict):
            for sub_k, sub_v in v.items():
                encoded.append((f"{k}[{sub_k}]", str(sub_v)))
        else:
            encoded.append((k, str(v)))

    url = f"{STRIPE_API}/{path}"
    data = urllib.parse.urlencode(encoded).encode("ascii") if method != "GET" else None
    if method == "GET" and encoded:
        url = f"{url}?{urllib.parse.urlencode(encoded)}"

    auth = base64.b64encode(f"{key}:".encode()).decode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 — Stripe API is whitelisted
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404 and not_found_ok:
            return None
        body = e.read().decode("utf-8", errors="replace")
        sys.stderr.write(f"Stripe API {method} /{path} → {e.code}: {body}\n")
        sys.exit(3)


def find_or_create_product() -> str:
    products = _stripe("GET", "products", limit=100, active="true")
    for p in products.get("data", []):
        if p.get("name") == PRODUCT_NAME:
            return p["id"]
    print(f"creating product '{PRODUCT_NAME}'...")
    p = _stripe(
        "POST",
        "products",
        name=PRODUCT_NAME,
        description="Project memory for Claude & Cursor — unlimited projects, "
                    "AI enrichment, MCP server access.",
        metadata={"plan_slug": "pro"},
    )
    return p["id"]


def find_or_create_price(product_id: str) -> str:
    prices = _stripe("GET", "prices", product=product_id, active="true", limit=100)
    for pr in prices.get("data", []):
        if (
            pr.get("unit_amount") == PRICE_AMOUNT_CENTS
            and pr.get("currency") == PRICE_CURRENCY
            and pr.get("recurring", {}).get("interval") == "month"
        ):
            return pr["id"]
    print("creating €8.99/month recurring price...")
    pr = _stripe(
        "POST",
        "prices",
        product=product_id,
        unit_amount=PRICE_AMOUNT_CENTS,
        currency=PRICE_CURRENCY,
        recurring={"interval": "month"},
        tax_behavior="exclusive",
        nickname="Vibecell Pro Monthly",
    )
    return pr["id"]


def find_or_create_annual_price(product_id: str) -> str:
    prices = _stripe("GET", "prices", product=product_id, active="true", limit=100)
    for pr in prices.get("data", []):
        if (
            pr.get("unit_amount") == PRICE_ANNUAL_CENTS
            and pr.get("currency") == PRICE_CURRENCY
            and pr.get("recurring", {}).get("interval") == "year"
        ):
            return pr["id"]
    print("creating €99.99/year recurring price...")
    pr = _stripe(
        "POST",
        "prices",
        product=product_id,
        unit_amount=PRICE_ANNUAL_CENTS,
        currency=PRICE_CURRENCY,
        recurring={"interval": "year"},
        tax_behavior="exclusive",
        nickname="Vibecell Pro Annual",
    )
    return pr["id"]


def find_or_create_launch_coupon() -> str:
    """The launch coupon — first 100 customers redeem for €30 off, applied
    `once` (so only the first year is discounted; renewals are full price)."""
    existing = _stripe("GET", f"coupons/{LAUNCH_COUPON_ID}", not_found_ok=True)
    if existing is not None and existing.get("id") == LAUNCH_COUPON_ID:
        print(f"coupon {LAUNCH_COUPON_ID}: found "
              f"({existing.get('times_redeemed', 0)}/{LAUNCH_COUPON_MAX} redeemed)")
        return LAUNCH_COUPON_ID
    print(f"creating launch coupon {LAUNCH_COUPON_ID} (€30 off, max 100 redemptions)...")
    c = _stripe(
        "POST",
        "coupons",
        id=LAUNCH_COUPON_ID,
        amount_off=LAUNCH_COUPON_AMOUNT_OFF,
        currency=PRICE_CURRENCY,
        duration="once",
        max_redemptions=LAUNCH_COUPON_MAX,
        name="Vibecell Launch — first 100 annual",
    )
    assert c is not None
    return c["id"]


def find_or_create_webhook() -> tuple[str, str | None]:
    """Returns (webhook_id, secret_or_None_if_existing)."""
    hooks = _stripe("GET", "webhook_endpoints", limit=100)
    for h in hooks.get("data", []):
        if h.get("url") == WEBHOOK_URL:
            return h["id"], None
    print("creating webhook endpoint...")
    h = _stripe(
        "POST",
        "webhook_endpoints",
        url=WEBHOOK_URL,
        enabled_events=WEBHOOK_EVENTS,
    )
    return h["id"], h.get("secret")


def update_plan_in_db(price_id: str) -> None:
    print("updating plans.stripe_price_id in the DB...")
    cmd = [
        "docker", "exec", DOCKER_PG_CONTAINER,
        "psql", "-U", "hangar", "-d", "hangar",
        "-c", f"UPDATE plans SET stripe_price_id='{price_id}' WHERE slug='pro'",
    ]
    subprocess.run(cmd, check=True, stdout=sys.stdout, stderr=sys.stderr)


def upsert_annual_plan_in_db(annual_price_id: str) -> None:
    """Insert/update the pro_annual plan row pointing at the annual Stripe price."""
    print("upserting plans (slug=pro_annual) in the DB...")
    sql = (
        "INSERT INTO plans (id, slug, name, stripe_price_id, monthly_price_eur_cents, "
        "max_projects, ai_enrichment_enabled, session_retention_days, trial_period_days) "
        "VALUES ('pro_annual_plan_row_______', 'pro_annual', 'Pro (annual)', "
        f"'{annual_price_id}', {PRICE_ANNUAL_CENTS}, NULL, true, 365, 0) "
        f"ON CONFLICT (slug) DO UPDATE SET stripe_price_id = EXCLUDED.stripe_price_id, "
        f"monthly_price_eur_cents = EXCLUDED.monthly_price_eur_cents"
    )
    cmd = [
        "docker", "exec", DOCKER_PG_CONTAINER,
        "psql", "-U", "hangar", "-d", "hangar",
        "-c", sql,
    ]
    subprocess.run(cmd, check=True, stdout=sys.stdout, stderr=sys.stderr)


def append_to_env_if_missing(key: str, value: str) -> None:
    """Add KEY=VALUE to ENV_FILE if KEY isn't already there. Doesn't print
    VALUE — preserves secrecy if value is a webhook signing secret."""
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = ""
    for line in existing.splitlines():
        if line.startswith(f"{key}="):
            print(f"{key} already present in {ENV_FILE}")
            return
    with open(ENV_FILE, "a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(f"{key}={value}\n")
    print(f"wrote {key} to {ENV_FILE}")


def restart_backend() -> None:
    print("restarting backend container...")
    subprocess.run(
        ["docker", "restart", "hangar-backend-1"],
        check=True, stdout=sys.stdout, stderr=sys.stderr,
    )


def main() -> None:
    product_id = find_or_create_product()
    print(f"product:  {product_id}")

    price_id = find_or_create_price(product_id)
    print(f"monthly:  {price_id}")
    append_to_env_if_missing("HANGAR_STRIPE_PRO_PRICE_ID", price_id)

    annual_price_id = find_or_create_annual_price(product_id)
    print(f"annual:   {annual_price_id}")
    append_to_env_if_missing("HANGAR_STRIPE_PRO_ANNUAL_PRICE_ID", annual_price_id)

    coupon_id = find_or_create_launch_coupon()
    print(f"coupon:   {coupon_id}")
    append_to_env_if_missing("HANGAR_STRIPE_LAUNCH_COUPON_ID", coupon_id)

    webhook_id, webhook_secret = find_or_create_webhook()
    print(f"webhook:  {webhook_id}")
    if webhook_secret:
        append_to_env_if_missing("HANGAR_STRIPE_WEBHOOK_SECRET", webhook_secret)
    else:
        env_has_secret = False
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                env_has_secret = "HANGAR_STRIPE_WEBHOOK_SECRET=" in f.read()
        except FileNotFoundError:
            pass
        if not env_has_secret:
            print(
                "WARNING: webhook already exists but HANGAR_STRIPE_WEBHOOK_SECRET\n"
                f"is not in {ENV_FILE}. Delete the webhook in Stripe Dashboard\n"
                f"({webhook_id}) and re-run this script to get a fresh secret."
            )

    update_plan_in_db(price_id)
    upsert_annual_plan_in_db(annual_price_id)
    restart_backend()
    print("DONE.")


if __name__ == "__main__":
    main()
