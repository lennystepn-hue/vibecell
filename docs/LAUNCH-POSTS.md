# Launch Posts · Drafts

These are starter copy — tweak voice / numbers / links per channel before
firing. Asset list at the bottom (image + GIF specs).

Vibecell URL: https://vibecell.dev · Pricing: https://vibecell.dev/pricing

Launch coupon: **LAUNCH69** — annual at €69.99 instead of €99.99 for the first
100 customers. Auto-applied on the annual checkout flow; mention it in the
post anyway because the strikethrough is what catches the eye.

---

## Twitter / X

**Hook (option A — broad):**

> Just launched Vibecell — the project console for shipping devs.
>
> One source of truth for every project you're building. Plugs straight into
> Claude, Cursor, Zed via MCP. Auto-logs commits, ticks todos from your
> commit messages, recovers context across sessions.
>
> €8.99/mo · €69.99/yr launch coupon (first 100). 7-day trial.
>
> https://vibecell.dev

**Hook (option B — punchy):**

> Lost track of which side-project you're shipping?
>
> Vibecell is the console: one click to pair Claude/Cursor → it auto-logs
> sessions, ships, decisions. No "I'll write a README later." No "where did
> we leave off."
>
> Launch coupon LAUNCH69 (€30 off annual, first 100 only).
>
> https://vibecell.dev

**Thread continuation (3-5 tweets):**

1. "What problem? Every weekend hack ends with: shipping notes scattered
   across Notion, Discord DMs, .md files, your terminal scrollback. Vibecell
   is the one cockpit your editor + your future self both look at."
2. "How? An MCP server your editor talks to natively. Claude/Cursor
   one-click install, OAuth handshake, done. From inside the editor you log
   sessions, complete todos, record ADR-lite decisions, ship versions."
3. "Why pay? €8.99/mo or €69.99/year (LAUNCH69 coupon). Free read-only mode
   if you cancel — your data stays accessible. GDPR export + delete are
   one-click endpoints."
4. "Built solo in Portugal · Vue 3 + FastAPI + Postgres on Hetzner Hel-3 ·
   open status page at https://status.vibecell.dev"

---

## Hacker News (Show HN)

**Title:** Show HN: Vibecell – Project console for shipping devs (MCP-native)

**Body:**

```
Hey HN,

I've been building Vibecell for the last few months, and it just shipped
a public launch.

The pitch: every weekend hack ends with shipping notes scattered across
Notion pages, Discord DMs, half-finished README sections, and `vim
TODO.md`. Vibecell is the cockpit your editor + your future self both
look at — one source of truth per project, plugged straight into Claude,
Cursor, Zed via MCP.

What's there at v1:
- One-click MCP pairing (claude://add-connector, cursor:// deeplink) so
  Claude can log sessions / tick todos / record decisions inline
- Auto-logging safety net: a 2-minute cron syncs GitHub commits → session
  rows + fuzzy-matches commit subjects to open todos and ticks them
- Project console: focus, todos, decisions, ships, telemetry, all
  per-project
- Cross-project portfolio with a 12-week activity heatmap so stagnation
  is visible
- BYOK Anthropic key option for AI features (handover briefs, retros,
  todo planning)
- Stripe + Stripe Tax for €8.99/mo or €99.99/year. LAUNCH69 coupon for
  the first 100 annual subscribers (€69.99/yr instead).

What's NOT there:
- Teams. v1 is solo-dev only by design — adding seats is a Spec-7
  problem.
- Mobile. Cockpit is laptop-first; pricing is high enough to keep it
  that way.
- A free tier. 7-day trial, then €8.99/mo. If that's a deal-breaker, the
  read-only mode after cancellation lets you keep accessing your data
  forever.

Stack: FastAPI + SQLAlchemy 2.x + Postgres + Redis on the backend,
Vue 3 + Pinia + Tailwind on the frontend, Rust CLI for terminal-side
helpers. MCP 2025-06 spec, OAuth 2.1 with PKCE.

Architecture decisions I'd love feedback on:
- The MCP server is the SAME FastAPI app — no separate server, single
  deployment artifact. Means a downed API takes the MCP with it, but
  also means there's one logging / auth / billing surface, no
  multi-process orchestration.
- The auto-tick from commit subject is fuzzy (≥ 1 score on a hand-rolled
  matcher). It's conservative on purpose — better to miss a tick than
  wrongly close an unrelated todo. Curious if the same heuristic
  generalises to other people's commit styles.

Status page: https://status.vibecell.dev/
Pricing: https://vibecell.dev/pricing
Try it: https://vibecell.dev/

Happy to answer anything.
```

---

## Bluesky

(280-char limit — same as Twitter A but trimmed)

> Just launched Vibecell — the project console for shipping devs.
>
> Plugs into Claude, Cursor, Zed via MCP. Auto-logs commits, ticks todos
> from commit messages, recovers context.
>
> €8.99/mo · LAUNCH69 €69.99/yr (first 100). 7-day trial.
>
> https://vibecell.dev

---

## Indie Hackers / Reddit r/SaaS / r/SideProject

**Title:** Vibecell · The MCP-native project console (one-click into Claude / Cursor)

(Use the HN body, with `## What's there at v1` / `## What's NOT` as the
section headers and a TL;DR at the top:)

> **TL;DR:** Vibecell is the cockpit your editor + your future self both look
> at. €8.99/mo, MCP-native, ship-tracking + auto-logging built in.

---

## Asset checklist

Render before posting:
- [ ] **Cover image (1500×500 Twitter banner):** screenshot of the project
      console with the activity heatmap visible, Cockpit theme
- [ ] **Square image (1200×1200):** the HeroOrb on dark background with
      "Vibecell · The project console for shipping devs." centered
- [ ] **GIF (≤ 8s):** record the one-click install flow — paste MCP URL into
      Claude Desktop → OAuth consent → land back on `/p` with green pulse
- [ ] **Demo video (≤ 60s):** voice-over walkthrough, post on YouTube +
      embed in HN thread reply

---

## Post-launch follow-ups (T+24h, T+1w)

- T+1h: monitor /api/v1/status, watch backend logs for unexpected exceptions
- T+24h: tweet "first day numbers" if interesting (signups, ships logged)
- T+72h: if HN gets traction, write the architecture deep-dive
- T+1w: "first week retro" thread on Bluesky + LinkedIn
- T+30d: blog post — what worked, what didn't, what's next (Spec-7 teams)
