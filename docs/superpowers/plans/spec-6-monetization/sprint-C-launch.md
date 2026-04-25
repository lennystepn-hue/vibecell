# Sprint C — Public Launch (Pricing, Legal, Onboarding, Status)

> **Goal:** Wrap a public-launch story around the now-monetized product. Pricing page, legal pages, onboarding wizard, status page. Then tweet.

**Estimated time:** 3 working days (~18 hours)

**Pre-flight check:**
- Sprint A + B complete and deployed.
- Stripe is in live mode, webhook signed with live secret.
- DNS for `status.vibecell.dev` resolves to Hetzner.

---

## Phase C1 — Pricing Page

**Files:**
- Create: `frontend/src/pages/Pricing.vue`
- Modify: `frontend/src/router/index.ts` (`/pricing` route, public)
- Modify: `frontend/src/pages/AnonLanding.vue` (link to /pricing in footer + hero CTA secondary)

- [ ] **Step 1: Pricing page layout**

Two-column comparison card (Free vs Pro), Stripe-inspired aesthetic to match the brand. Each column lists features with check/x icons. Pro column has the orange gradient ring; CTA buttons "Get started free" / "Go Pro €8/mo".

Content:

| Feature | Free | Pro |
|---|---|---|
| Projects | 1 | Unlimited |
| AI enrichment from GitHub | — | ✓ |
| Session retention | 7 days | Unlimited |
| MCP server access | ✓ | ✓ |
| Auto-screenshot cron | — | ✓ |
| Commit-sync cron | — | ✓ |
| Email support | — | ✓ |

- [ ] **Step 2: FAQ section**

8–10 questions: "What's MCP?", "Can I cancel anytime?", "Do you offer refunds?", "EU VAT?", "Is my data encrypted?", "What if I exceed limits?", "Team plans?", "Self-hosting?".

- [ ] **Step 3: Anchor links from landing**

`AnonLanding.vue` hero secondary button → `/pricing`. Footer link too.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(public): /pricing page with Free vs Pro comparison + FAQ"
```

---

## Phase C2 — Legal Pages (Impressum + ToS + Privacy)

**Why:** German law (TMG §5) requires Impressum for any commercial offering. EU GDPR requires Privacy Policy. ToS protects you in disputes.

**Disclaimer:** I (Claude) am not a lawyer. The drafts below are skeleton-only — Lenny MUST have a German Datenschutzanwalt review them before launch. Iubenda or Termly templates are also acceptable starting points.

**Files:**
- Create: `frontend/src/pages/Imprint.vue` (Impressum)
- Create: `frontend/src/pages/Privacy.vue`
- Create: `frontend/src/pages/Terms.vue`
- Modify: `frontend/src/components/Footer.vue` (link to all three)

- [ ] **Step 1: Imprint draft**

Required content per TMG §5:
- Full legal name + address (Lenny's registered business address — Einzelunternehmen is fine)
- Contact: email + phone
- Tax-ID (Umsatzsteuer-ID) if VAT-registered
- Responsible-for-content: same person, "Verantwortlich i.S.d. § 18 Abs. 2 MStV"

Lenny: please paste your address + Steuernummer/USt-ID into the page directly. Do not commit fake placeholders to git history.

- [ ] **Step 2: Privacy Policy draft**

Use [iubenda](https://iubenda.com) or [termly](https://termly.io) free generator as starting point. Must explicitly mention:
- Data we collect (email, OAuth GitHub data, project metadata, MCP audit logs, IP for rate-limiting)
- Third parties (Resend for email, Stripe for billing, GitHub OAuth, Anthropic for AI enrichment, Sentry for errors, Backblaze for backups)
- User rights (GDPR Art. 15-22) — access, rectification, deletion, portability — link to `/settings/account`
- Cookie disclosure (we set `vibecell_session` httpOnly cookie)
- Contact: same email as Imprint

- [ ] **Step 3: Terms of Service draft**

Topics: account creation, acceptable use (no scraping API, no resale), liability cap (€100 or one month's fees), refund policy (Stripe-default = no refund after 14-day EU withdrawal period for digital services unless user invoked Widerrufsrecht at signup), termination, governing law (Germany), dispute resolution (Hamburg/Berlin court — pick yours).

- [ ] **Step 4: Footer links + 14-day Widerrufsbelehrung at checkout**

EU consumer law requires a "Right of Withdrawal" notice **at the moment of purchase**. Add a checkbox at Stripe Checkout (configured in Stripe dashboard → Customer-facing → Customer message): _"Mit Klick auf 'Zahlen' verzichte ich auf mein 14-tägiges Widerrufsrecht und stimme zu, dass die Leistung sofort beginnt."_

- [ ] **Step 5: Have a lawyer review (NOT a code step)**

Track in Vibecell as a `todo` with `assignee=lenny`, not auto-completable. **DO NOT skip this step.**

- [ ] **Step 6: Commit (placeholder — Lenny fills in real legal copy)**

```bash
git commit -m "feat(legal): Imprint + Privacy + Terms (DE compliance)"
```

---

## Phase C3 — Onboarding Wizard (First-Project)

**Why:** Today after signup, the user lands on an empty dashboard. No friction for a power-user, but for a paying customer this is the "aha"-moment we waste.

**Files:**
- Create: `frontend/src/pages/Onboarding.vue` (3-step wizard)
- Modify: `frontend/src/pages/Dashboard.vue` (redirect to /onboarding if `projects.length === 0`)
- Modify: `frontend/src/router/index.ts` (`/onboarding` route)

- [ ] **Step 1: 3-step wizard**

Step 1 — "Add your first project":
- Two big buttons: "Import from GitHub" (uses existing `/import/github` flow) OR "Create blank"

Step 2 — "Connect Claude (MCP)":
- Show one-line install command: `curl -fsSL https://vibecell.dev/install.sh | bash && vibecell pair`
- Live indicator polls `/me/mcp-paired` — once true, advances automatically.
- "Skip for now" link.

Step 3 — "You're done":
- Confetti, link to dashboard.

- [ ] **Step 2: Empty-state on Dashboard**

If `projects.length === 0`, redirect to `/onboarding`. Otherwise show normal dashboard.

- [ ] **Step 3: Vitest test**

```typescript
test("new user lands on onboarding", async () => {
  // mock projects.length === 0
  router.push("/dashboard");
  await flushPromises();
  expect(router.currentRoute.value.path).toBe("/onboarding");
});
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(onboarding): 3-step wizard for first-project + MCP pairing"
```

---

## Phase C4 — Status Page

**Why:** Vertrauen. When the API is down, users want a non-Vibecell URL that says so. Bonus: shows we care about uptime.

**Files:**
- Create: `frontend/src/pages/Status.vue` (calls `/api/v1/status` and renders)
- Create: `backend/app/routes/status.py`
- Modify: DNS — `status.vibecell.dev` CNAME to `vibecell.dev`
- Modify: Caddy config — route `status.vibecell.dev` to `/status`

- [ ] **Step 1: Backend `/api/v1/status`**

```python
@router.get("/status")
async def status(session: SessionDep, redis: RedisDep):
    checks = {
        "database": await check_db(session),
        "redis": await check_redis(redis),
        "anthropic": await check_anthropic(),  # HEAD request to api.anthropic.com
        "stripe": await check_stripe(),
        "github": await check_github(),
    }
    overall = "operational" if all(c["ok"] for c in checks.values()) else "degraded"
    return {"overall": overall, "checks": checks, "checked_at": now_iso()}
```

- [ ] **Step 2: Frontend `/status`**

Plain page, no auth required. Lists each dependency with green/yellow/red dot. Auto-refreshes every 30 s. Shows last-checked timestamp.

- [ ] **Step 3: Caddy + DNS**

Route `status.vibecell.dev` → same Caddy reverse-proxy, but force path to `/status`.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(public): /status health page + status.vibecell.dev"
```

---

## Phase C5 — Launch Checklist

**Why:** Last-mile sanity. Each checkbox is a 5-min thing that's easy to forget.

- [ ] All Sprint A done-definition items remain checked
- [ ] All Sprint B done-definition items remain checked
- [ ] One full external test: brand-new browser profile → vibecell.dev → signup → verify email → import GitHub repo → run `vibecell pair` → see project in dashboard → upgrade to Pro → run AI enrichment → cancel → confirm demoted to free
- [ ] Stripe live-mode webhook returns 200 on `customer.subscription.created` (test via dashboard: "Send test webhook")
- [ ] EU VAT setup: Stripe Tax shows tax rates for DE/AT/FR; test customer with each address gets correct VAT
- [ ] Sentry receives a real production event (or seeded one)
- [ ] PG-backup ran today; latest file in `/srv/hangar/backups`
- [ ] Restore drill: schedule one for 14 days post-launch
- [ ] DNS: `vibecell.dev`, `www.vibecell.dev`, `status.vibecell.dev` all resolve
- [ ] HTTPS: A+ on ssllabs.com
- [ ] Imprint/ToS/Privacy reviewed by lawyer (or accepted as risk-with-disclaimer)
- [ ] `/pricing` looks good on mobile (responsive pass)
- [ ] Twitter / Bluesky / Hacker News launch posts drafted, reviewed, scheduled
- [ ] Vibecell project state cleaned up: pricing decision committed as `decision`, `current_focus` updated to "v1 launched"
- [ ] Tag `v0.6.C-launch && git push --tags`
- [ ] Tag `v1.0.0 && git push --tags` (this is THE launch)

---

## Sprint C Done-Definition

- [ ] Tagged `v1.0.0`
- [ ] First non-Lenny user signs up + upgrades + AI-enriches a project end-to-end
- [ ] First Stripe payout received (after Stripe's payout schedule, ~7 days)
- [ ] Twitter/HN post is live and getting feedback
