<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import HeroOrb from "@/components/landing/HeroOrb.vue";
import DashboardPreview from "@/components/landing/DashboardPreview.vue";
import MarketingHeader from "@/components/marketing/MarketingHeader.vue";
import ProjectOrb from "@/components/ui/ProjectOrb.vue";
import { useRouteMeta } from "@/composables/useMeta";
import { useAuthStore } from "@/stores/auth";

useRouteMeta({
  title: "Vibecell — AI project management & MCP-native console for shipping devs",
  description:
    "AI-native project console for indie devs. One source of truth per project — todos, sessions, decisions, ships — plugged straight into Claude Code, Cursor, Zed via MCP. €8.99/mo · 7-day trial.",
  canonical: "https://vibecell.dev/",
});

const router = useRouter();
const auth = useAuthStore();

function goSignIn() {
  router.push(auth.isAuthed ? "/p" : "/login");
}

function scrollToDemo() {
  document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" });
}

// Animated counter for stat strip. MCP-tools count is the live registry
// length on the backend (mirrors the "X tools registered" string returned
// by /api/v1/status). Bump in lockstep with new tools.
const counters = ref([
  { value: 0, target: 49, label: "MCP tools", suffix: "" },
  { value: 0, target: 5, label: "IDE clients", suffix: "" },
  { value: 0, target: 2, label: "setup", suffix: "s" },
  { value: 0, target: 0, label: "install", suffix: "" },
]);

// MCP tool catalog — 6 capability cards. Seeded so every category gets
// its own orb (consistent visual language with the rest of the page).
// One sentence of plain English + a single signature tool name.
// MCP tool buckets — counts must sum to the live total (49 as of f82141c).
// Re-bucket carefully when adding new tools so the hero stat strip
// (49 above) and these per-category counts stay consistent.
const mcpGroups = [
  {
    seed: "mcp-spawn",
    tag: "Spawn",
    count: 3,
    blurb: "Describe an idea in Claude — a project appears in the dashboard with stack, tags, pitch pre-filled.",
    signature: "vibecell_create_project",
    accent: true,
  },
  {
    seed: "mcp-read",
    tag: "Read",
    count: 12,
    blurb: "Claude pulls the full project aggregate, the AI primer, search history, generates resurrection briefs.",
    signature: "vibecell_active",
  },
  {
    seed: "mcp-write",
    tag: "Write",
    count: 20,
    blurb: "Every session, decision, ship, URL or script Claude touches lands as a one-line tool call.",
    signature: "vibecell_log_session",
  },
  {
    seed: "mcp-todos",
    tag: "Todos",
    count: 6,
    blurb: "Plan work as visible batches. Claude ticks each one off with a commit note as it ships.",
    signature: "vibecell_todo_batch_add",
  },
  {
    seed: "mcp-secrets",
    tag: "Secrets",
    count: 4,
    blurb: "Workspace-scoped vault. References to 1Password / Bitwarden, or inline-encrypted with a DEK.",
    signature: "vibecell_secret_get_value",
  },
  {
    seed: "mcp-ai",
    tag: "AI",
    count: 4,
    blurb: "BYOK Anthropic key. Goal-to-todos planning, launch copy, retros, morning resume brief.",
    signature: "vibecell_ai_plan_todos",
  },
];

onMounted(() => {
  const duration = 1400;
  const step = 16;
  const start = Date.now();
  function tick() {
    const elapsed = Date.now() - start;
    const progress = Math.min(elapsed / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    counters.value.forEach((c) => {
      c.value = Math.round(ease * c.target);
    });
    if (progress < 1) setTimeout(tick, step);
  }
  setTimeout(tick, 400);
  loadLaunchStatus();
});

interface LaunchStatus { active: boolean; remaining: number; max: number }
const launch = ref<LaunchStatus>({ active: false, remaining: 0, max: 100 });
async function loadLaunchStatus() {
  try {
    const r = await fetch("/api/v1/billing/launch-status");
    if (r.ok) launch.value = await r.json();
  } catch { /* silent */ }
}

// Removed the generic feature grid — it repeated what the orb-showcase +
// MCP catalog + session-mockup already cover. Keeping the surface tight.

// Showcase seeds → each orb is an illustrated hint at a capability. The seed
// string also doubles as a stable key for the ProjectOrb hash so the colors
// stay consistent across the page. Keep labels terse, blurbs one sentence.
const orbShowcase = [
  {
    seed: "auto-catalog",
    label: "auto-catalog",
    blurb: "Reads README + manifests, fills stack, infra, tags on import.",
  },
  {
    seed: "session-log",
    label: "session-log",
    blurb: "Every git commit auto-logs a session row. Zero cognitive tax.",
  },
  {
    seed: "env-drift",
    label: "env-drift",
    blurb: "Fingerprints manifests. Surfaces package.json drift between sessions.",
  },
  {
    seed: "mcp-tools",
    label: "mcp-tools",
    blurb: "49 typed endpoints Claude can drive — create, log, ship, search.",
  },
  {
    seed: "portfolio",
    label: "portfolio",
    blurb: "Heatmap across every project. Stagnation flagged before it rots.",
  },
  {
    seed: "resume-brief",
    label: "resume-brief",
    blurb: "Morning \"where the fuck was I\" summary from last session + next step.",
  },
  {
    seed: "secrets-vault",
    label: "secrets",
    blurb: "1Password / Bitwarden paths OR AES-256 inline. Never leaves your box.",
  },
  {
    seed: "ship-events",
    label: "ship-it",
    blurb: "One call. Generates changelog, launch copy, tweet drafts.",
  },
];

const spawnPaths = [
  {
    icon: "mcp",
    tag: "via Claude Code",
    title: "Describe your idea, Claude creates it",
    body: "Say \"I want to build a dashboard for tracking X\" in Claude Code — Vibecell spawns the project with stack, tags, environments + commands pre-filled. Zero form.",
  },
  {
    icon: "github",
    tag: "via GitHub import",
    title: "Pull your entire org in one click",
    body: "Connect GitHub, select repos, Haiku reads each README + manifest and writes pitch, stack, infra, env URLs, run-scripts. Live in seconds.",
  },
  {
    icon: "manual",
    tag: "via dashboard",
    title: "Manual control when you want it",
    body: "Name, emoji (optional — orb is auto), pitch, status. Done. Claude starts populating the rest the moment you open a session in the repo.",
  },
];

const steps = [
  {
    num: "01",
    title: "Register your workspace",
    body: "Create a free account with magic-link or passkey. Your workspace is ready in under 10 seconds.",
  },
  {
    num: "02",
    title: "Connect Claude (or any MCP client)",
    body: "Copy one config line into your claude_desktop_config.json. Vibecell appears as a tool server instantly.",
  },
  {
    num: "03",
    title: "Just work — context follows you",
    body: "Switch projects, switch machines, switch AI clients. Your context is always there. Ship more, context-switch less.",
  },
];
</script>

<template>
  <div class="min-h-screen text-fg-primary overflow-x-hidden" style="background: #070b10">

    <!-- ─── Nav (shared MarketingHeader) ────────────────────────────────── -->
    <MarketingHeader cta="Get started →" />

    <!-- ─── Hero ─────────────────────────────────────────────────────────── -->
    <!-- Mobile note: min-h drops on small viewports so the section sizes to
         its content (copy + orb stack) instead of forcing 88vh and leaving
         the orb floating below the fold with awkward whitespace.
         pb-0 on mobile so the next section's bg-bloom flows in cleanly
         without a visible cutoff between hero and "Works with" strip. -->
    <section class="relative flex items-center overflow-hidden pt-20 pb-8 md:pb-12 md:min-h-[88vh]">
      <!-- Subtle grid background -->
      <div class="absolute inset-0 pointer-events-none"
        style="background-image: linear-gradient(rgba(138,180,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(138,180,255,0.03) 1px, transparent 1px); background-size: 60px 60px" />
      <!-- Orb-palette gradient blooms — soft violet + mint + pink washes that
           tie the hero bg into the orb's own colors. Sized in vmax so they
           shrink on mobile instead of overflowing the viewport sideways. -->
      <div class="absolute -top-40 -left-40 rounded-full pointer-events-none"
        style="width: 60vmax; height: 60vmax; max-width: 780px; max-height: 780px; background: radial-gradient(circle, rgba(181,146,255,0.10) 0%, transparent 65%); filter: blur(20px)" />
      <div class="absolute top-1/3 right-[-20%] rounded-full pointer-events-none"
        style="width: 55vmax; height: 55vmax; max-width: 700px; max-height: 700px; background: radial-gradient(circle, rgba(92,200,164,0.09) 0%, transparent 65%); filter: blur(20px)" />
      <div class="absolute bottom-0 left-1/2 -translate-x-1/2 rounded-full pointer-events-none"
        style="width: 80vmax; height: 32vmax; max-width: 900px; max-height: 400px; background: radial-gradient(ellipse, rgba(255,107,157,0.06) 0%, transparent 70%); filter: blur(30px)" />

      <!-- Mobile: gap-8 instead of gap-12 (stacked layout doubles vertical
           cost). py-12 instead of py-20 — the outer pt-20 already gave us
           room under the fixed nav. -->
      <div class="relative z-10 w-full max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-8 lg:gap-12 items-center py-12 md:py-20">

        <!-- Left: copy — ruthlessly trimmed. H1 + one-line subhead + CTAs. -->
        <div>
          <!-- clamp shrinks safely on narrow viewports (2.1rem = 33.6px on
               iPhone SE) and tops out at 4.4rem on widescreens. -->
          <h1 class="font-sans font-semibold mb-6 leading-[1.04] tracking-tight"
            style="font-size: clamp(2.1rem, 5.5vw, 4.4rem); letter-spacing: -0.04em; color: #ffffff">
            The project console<br>
            for
            <!-- Same color band as the orb (mint → violet → mint → pink) —
                 sweeps across the text on the same 18s cadence as the orb's
                 aurora-rotate, so the headline and the orb feel sourced
                 from the same animated palette. -->
            <span class="aurora-text">shipping devs.</span>
          </h1>

          <p class="mb-9 leading-relaxed max-w-md"
            style="font-size: 1.05rem; color: #cfd4dc; line-height: 1.55">
            One source of truth for every weekend hack, side-project,
            and full app — with an MCP server your AI already speaks.
          </p>

          <div class="flex flex-wrap gap-3 mb-3">
            <button
              class="px-5 py-2.5 rounded-md font-mono font-semibold text-[12px] transition-opacity hover:opacity-90 tracking-wider uppercase"
              style="background: #5cc8a4; color: #070b10; box-shadow: 0 0 20px rgba(92,200,164,0.18)"
              @click="goSignIn">
              {{ auth.isAuthed ? 'Open dashboard →' : 'Start 7-day trial →' }}
            </button>
            <button
              class="px-5 py-2.5 rounded-md font-mono text-[12px] transition-opacity hover:opacity-100 tracking-wider uppercase"
              style="border: 1px solid rgba(138,180,255,0.2); color: #cfd4dc; background: transparent; opacity: 0.85"
              @click="scrollToDemo">
              See how it works ↓
            </button>
          </div>

          <!-- Two friction-free shortcut paths below the primary trial CTA:
               1. AI-paste install for users whose editor already speaks MCP.
               2. Google one-click sign-in for everyone else.
               Both are inline links rather than buttons — keeps the primary
               accent on the green "Start 7-day trial" button per the
               .impeccable.md "single accent per surface" rule. -->
          <p class="mb-2 font-mono text-[11px]" style="color: #cfd4dc; letter-spacing: 0.02em">
            <span aria-hidden="true" style="color: #5cc8a4">✦</span>
            Already in Claude / Cursor / Zed?
            <RouterLink
              to="/install"
              class="underline-offset-2 hover:underline"
              style="color: #5cc8a4"
            >Paste one prompt — AI installs itself →</RouterLink>
          </p>
          <a
            v-if="!auth.isAuthed"
            href="/api/v1/auth/google/start?next=%2Fp"
            class="mb-7 inline-flex items-center gap-2 font-mono text-[11px] hover:underline underline-offset-2"
            style="color: #cfd4dc; letter-spacing: 0.02em"
          >
            <svg width="12" height="12" viewBox="0 0 18 18" aria-hidden="true">
              <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.25-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z"/>
              <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z"/>
              <path fill="#FBBC05" d="M3.964 10.706A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.038l3.007-2.332Z"/>
              <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.962L3.964 7.294C4.672 5.167 6.656 3.58 9 3.58Z"/>
            </svg>
            <span>Or sign up with Google — one click →</span>
          </a>
          <div v-else class="mb-7" />


          <!-- Feature signal — surfaces the actual product surface
               (dashboard + MCP tools + cron + secrets + history) rather
               than infrastructure. Mono-label cadence, no marketing copy. -->
          <p class="font-mono text-[11px]" style="color: #5e7088; letter-spacing: 0.04em">
            dashboard · 49 MCP tools · auto-cron · session log · workspace secrets
          </p>
        </div>

        <!-- Right: Hero orb — slowly-rotating aurora-glass sphere. Desktop
             only. On mobile/tablet the headline + CTAs already carry the
             page and the orb's halo + heavy drop-shadows fight the section
             edges in ways that read as visual noise. Hidden below lg so
             the stacked mobile layout stays tight (copy + buttons, no
             400px sphere consuming half the viewport). -->
        <div class="relative hidden lg:flex items-center justify-center">
          <div
            class="relative w-full"
            style="aspect-ratio: 1; max-width: 520px; margin: auto"
          >
            <HeroOrb class="w-full h-full" />
          </div>
        </div>
      </div>
    </section>

    <!-- ─── "Works with" logo strip ────────────────────────────────────── -->
    <section class="relative px-6 py-8 -mt-8">
      <div class="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-center gap-6 sm:gap-10">
        <p class="font-mono text-[10px] tracking-[0.18em] uppercase" style="color: #5e7088">
          Works with
        </p>
        <div class="flex flex-wrap items-center justify-center gap-x-8 gap-y-4 opacity-80">
          <!-- Brand logomarks below come from simple-icons.org (CC0 / public
               domain). All rendered fill="currentColor" so they pick up the
               cockpit-grey text color and stay theme-stable in light/dark.
               Stylistically subordinate to the wordmark next to them — the
               icons read as a tiny prefix, not a heavy logo wall. -->
          <!-- Claude / Anthropic — angular A-mark (simple-icons: anthropic) -->
          <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: #cfd4dc; font-size: 14px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M17.304 3.541h-3.672l6.696 16.918H24Zm-10.608 0L0 20.459h3.744l1.37-3.553h7.005l1.37 3.553h3.744L10.536 3.541Zm-.371 10.223 2.291-5.946 2.292 5.946Z"/>
            </svg>
            <span class="font-mono text-[13px]">Claude</span>
          </span>
          <!-- Cursor — official cursor mark (simple-icons: cursor) -->
          <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: #cfd4dc; font-size: 14px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M11.925 24l10.425-6V6L11.925 0 1.5 6v12l10.425 6zm10.425-6L11.925 12 1.5 18l10.425 6 10.425-6zm0-12L11.925 12V0l10.425 6zM1.5 6v12l10.425-6V0L1.5 6z"/>
            </svg>
            <span class="font-mono text-[13px]">Cursor</span>
          </span>
          <!-- OpenAI — petal/knot logomark (simple-icons: openai) -->
          <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: #cfd4dc; font-size: 14px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.998-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.142-.08 4.778-2.758a.795.795 0 0 0 .393-.681v-6.737l2.02 1.168a.07.07 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.495 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .781 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.677l5.815 3.354-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855L13.103 8.364 15.12 7.2a.076.076 0 0 1 .07 0l4.83 2.792a4.494 4.494 0 0 1-.676 8.104V12.42a.79.79 0 0 0-.407-.667zm2.01-3.024-.142-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.062l4.83-2.787a4.5 4.5 0 0 1 6.681 4.66zM8.307 12.863l-2.02-1.164a.08.08 0 0 1-.038-.057V6.074a4.5 4.5 0 0 1 7.376-3.454l-.142.081L8.704 5.46a.795.795 0 0 0-.393.681zm1.098-2.366 2.602-1.5 2.607 1.5v3l-2.598 1.5-2.607-1.5Z"/>
            </svg>
            <span class="font-mono text-[13px]">OpenAI</span>
          </span>
          <!-- Zed — angular Z arrow (simple-icons: zedindustries) -->
          <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: #cfd4dc; font-size: 14px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M11.999 0a11.999 11.999 0 1 0 0 23.998A11.999 11.999 0 0 0 12 0Zm5.997 5.987-7.992 7.991h7.992v3.998H5.962v-3.998l7.991-7.991H5.962V1.989h12.034Z"/>
            </svg>
            <span class="font-mono text-[13px]">Zed</span>
          </span>
          <!-- Continue.dev — chevron continuation mark. Their actual logo
               is a stylised "carrot/play" pair; this is a faithful inline
               approximation since they don't ship a CC0 SVG. -->
          <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: #cfd4dc; font-size: 14px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M3 5.5v13a1 1 0 0 0 1.546.838l8.5-5.5a1 1 0 0 0 0-1.676l-8.5-5.5A1 1 0 0 0 3 5.5Z" opacity=".5"/>
              <path d="M11 5.5v13a1 1 0 0 0 1.546.838l8.5-5.5a1 1 0 0 0 0-1.676l-8.5-5.5A1 1 0 0 0 11 5.5Z"/>
            </svg>
            <span class="font-mono text-[13px]">Continue</span>
          </span>
        </div>
      </div>
    </section>

    <!-- ─── Dashboard preview — SEE what you get, don't just read it. ───── -->
    <section class="relative px-6 pb-24">
      <!-- Ambient glow under the preview frame -->
      <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 h-[500px] pointer-events-none"
        style="background: radial-gradient(ellipse 60% 60% at 50% 50%, rgba(92,200,164,0.06) 0%, transparent 70%)" />
      <div class="relative max-w-[1280px] mx-auto">
        <DashboardPreview />
        <!-- Caption under the mockup -->
        <p class="text-center mt-6 font-mono text-[11px] tracking-[0.1em] uppercase"
          style="color: #5e7088">
          Your actual dashboard — live, realtime, Claude-driven
        </p>
      </div>
    </section>

    <!-- ─── Stats strip ──────────────────────────────────────────────────── -->
    <div class="border-y" style="border-color: rgba(138,180,255,0.08); background: rgba(20,33,50,0.3)">
      <div class="max-w-4xl mx-auto px-6 py-8 grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
        <div v-for="c in counters" :key="c.label">
          <p class="font-mono font-bold mb-1" style="font-size: 2rem; color: #5cc8a4; letter-spacing: -0.04em">
            {{ c.value }}{{ c.suffix }}
          </p>
          <p class="font-mono text-[11px] uppercase tracking-[0.1em]" style="color: #5e7088">
            {{ c.label }}
          </p>
        </div>
      </div>
    </div>

    <!-- ─── MCP-native: tool catalog ─────────────────────────────────────── -->
    <section class="relative py-16 md:py-28 px-6 overflow-hidden">
      <!-- Ambient fabric: terminal-green wash with mesh -->
      <div class="absolute inset-0 pointer-events-none"
        style="background:
          radial-gradient(ellipse 60% 40% at 50% 20%, rgba(92,200,164,0.07) 0%, transparent 70%),
          radial-gradient(ellipse 40% 50% at 20% 80%, rgba(138,180,255,0.05) 0%, transparent 70%)" />

      <div class="relative z-10 max-w-6xl mx-auto">
        <!-- Heading block -->
        <div class="text-center mb-4">
          <p class="font-mono text-[11px] uppercase tracking-[0.15em] mb-3" style="color: #5cc8a4">
            <span class="w-1.5 h-1.5 rounded-full bg-signal-green inline-block mr-2 align-middle animate-pulse" />
            MCP-native, not MCP-compatible
          </p>
          <h2 class="font-semibold leading-tight mb-4"
            style="font-size: clamp(1.8rem, 3.5vw, 2.6rem); letter-spacing: -0.03em; color: #ffffff">
            49 tools. One mental model.<br>
            <span style="color: #8ba1bd">Claude drives everything.</span>
          </h2>
          <p class="max-w-2xl mx-auto leading-relaxed"
            style="font-size: 14px; color: #8ba1bd; line-height: 1.7">
            Vibecell isn&rsquo;t an app that happens to talk MCP. It&rsquo;s a set of 49 typed tool
            endpoints that Claude (or Cursor, or Zed) can wire itself into in under 10 seconds.
            Every capability in the dashboard &mdash; creating projects, logging sessions, tracking
            drift, managing secrets &mdash; is a first-class tool call.
          </p>
        </div>

        <!-- Tool-group list: 6 rows, each with orb + meta + blurb + signature tool.
             Horizontal stripe layout (not cards) to DIFFERENTIATE from the
             card patterns used elsewhere on the page. Reads like a reference
             index — dense, scannable, calm. -->
        <div class="mt-16 divide-y" style="border-color: rgba(138,180,255,0.08); border-top: 1px solid rgba(138,180,255,0.08); border-bottom: 1px solid rgba(138,180,255,0.08)">
          <!-- Mobile layout: orb + (tag/count + signature pill) on row 1,
               blurb hidden. Desktop: original 4-col grid with rigid 160px
               middle column + 1fr blurb. The grid-cols only kicks in at md;
               below that we use flex-wrap so nothing overflows. -->
          <div
            v-for="g in mcpGroups"
            :key="g.tag"
            class="flex flex-wrap items-center gap-x-4 gap-y-2 py-5 px-2 transition-colors hover:bg-white/[0.02]
                   md:grid md:grid-cols-[auto_160px_1fr_auto] md:gap-6"
            style="border-top: 1px solid rgba(138,180,255,0.08)"
          >
            <!-- Orb — the category identity -->
            <ProjectOrb :seed="g.seed" :size="44" />

            <!-- Tag + count — flex-1 on mobile so it pushes the pill to
                 the right edge; auto on desktop because the grid handles it. -->
            <div class="flex-1 md:flex-none min-w-0">
              <p class="font-semibold truncate"
                style="font-size: 15px; color: #ffffff; letter-spacing: -0.01em">
                {{ g.tag }}
              </p>
              <p class="font-mono tabular-nums mt-0.5"
                :style="g.accent
                  ? 'font-size: 11px; color: #5cc8a4'
                  : 'font-size: 11px; color: #5e7088'">
                {{ g.count }} tools
              </p>
            </div>

            <!-- Blurb — only shown md+ to keep mobile rows compact. -->
            <p class="hidden md:block leading-relaxed"
              style="font-size: 13px; color: #8ba1bd; line-height: 1.55">
              {{ g.blurb }}
            </p>

            <!-- Signature tool name. order-last on mobile keeps it on the
                 same first row as the tag block; on desktop the grid puts
                 it at the far right anyway. -->
            <span
              class="font-mono text-[11px] px-2.5 py-1 rounded-md whitespace-nowrap tabular-nums shrink-0"
              :style="g.accent
                ? 'background: rgba(92,200,164,0.08); color: #a9e5cc; border: 1px solid rgba(92,200,164,0.18)'
                : 'background: rgba(7,11,16,0.5); color: #8ba1bd; border: 1px solid rgba(138,180,255,0.1)'"
            >
              {{ g.signature }}
            </span>
          </div>
        </div>

        <!-- Footnote strip -->
        <div class="mt-12 flex flex-wrap items-center justify-center gap-4 sm:gap-8 font-mono text-[11px]"
          style="color: #5e7088">
          <span class="flex items-center gap-2">
            <span class="w-1 h-1 rounded-full bg-signal-green" />
            Streamable HTTP transport
          </span>
          <span>·</span>
          <span>OAuth 2.1 + bearer token</span>
          <span>·</span>
          <span>Pydantic-typed args</span>
          <span>·</span>
          <span>Graceful fallback on missing key</span>
        </div>
      </div>
    </section>

    <!-- ─── Orb feature storytelling ─────────────────────────────────────── -->
    <section class="relative py-16 md:py-28 px-6 overflow-hidden">
      <!-- Subtle radial glow behind the orbs — same aesthetic as the hero -->
      <div class="absolute inset-0 pointer-events-none"
        style="background: radial-gradient(ellipse 70% 50% at 50% 40%, rgba(138,180,255,0.06) 0%, transparent 70%)" />
      <div
        class="absolute top-1/3 left-1/4 w-[500px] h-[500px] rounded-full pointer-events-none"
        style="background: radial-gradient(circle, rgba(181,146,255,0.05) 0%, transparent 70%); filter: blur(40px)"
      />
      <div
        class="absolute top-1/2 right-1/4 w-[500px] h-[500px] rounded-full pointer-events-none"
        style="background: radial-gradient(circle, rgba(92,200,164,0.05) 0%, transparent 70%); filter: blur(40px)"
      />

      <div class="relative z-10 max-w-6xl mx-auto">
        <!-- Heading -->
        <div class="text-center mb-16">
          <p class="font-mono text-[11px] uppercase tracking-[0.15em] mb-3" style="color: #5cc8a4">
            Eight things that just happen
          </p>
          <h2 class="font-semibold leading-tight mb-4"
            style="font-size: clamp(1.6rem, 3vw, 2.4rem); letter-spacing: -0.03em; color: #ffffff">
            One orb, one superpower.<br>
            <span style="color: #8ba1bd">All of them on by default.</span>
          </h2>
          <p class="max-w-xl mx-auto leading-relaxed" style="font-size: 14px; color: #8ba1bd">
            Pick any orb. Everything behind it runs without config, without ceremony,
            without you ever opening a form. This is what you wire up once and forget forever.
          </p>
        </div>

        <!-- Orb feature grid: 4 cols × 2 rows, each orb + feature label + micro blurb -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-10 mb-20 max-w-5xl mx-auto">
          <div
            v-for="o in orbShowcase"
            :key="o.seed"
            class="flex flex-col items-center gap-3 text-center transition-transform duration-300 hover:-translate-y-1"
          >
            <ProjectOrb :seed="o.seed" :size="72" />
            <span class="font-mono text-[11px] tracking-wide mt-1"
              style="color: #cfd4dc; letter-spacing: 0.03em">
              {{ o.label }}
            </span>
            <p class="max-w-[180px] leading-snug"
              style="font-size: 11.5px; color: #8ba1bd; line-height: 1.55">
              {{ o.blurb }}
            </p>
          </div>
        </div>

        <!-- Spawn paths — three sub-sections -->
        <div class="text-center mb-10">
          <p class="font-mono text-[11px] uppercase tracking-[0.15em] mb-3" style="color: #5cc8a4">
            Three ways to spawn a project
          </p>
          <h3 class="font-semibold"
            style="font-size: clamp(1.3rem, 2.4vw, 1.8rem); letter-spacing: -0.02em; color: #ffffff">
            Start from a conversation, a repo, or a blank slate
          </h3>
        </div>

        <div class="grid md:grid-cols-3 gap-5">
          <div
            v-for="(s, i) in spawnPaths"
            :key="s.tag"
            class="rounded-xl p-6 transition-all duration-300 hover:-translate-y-[2px]"
            :style="i === 0
              ? 'background: rgba(92,200,164,0.06); border: 1px solid rgba(92,200,164,0.2); box-shadow: 0 0 32px rgba(92,200,164,0.04)'
              : 'background: rgba(20,33,50,0.45); border: 1px solid rgba(138,180,255,0.1)'"
          >
            <!-- Icon tile -->
            <div class="w-10 h-10 rounded-lg flex items-center justify-center mb-5"
              :style="i === 0
                ? 'background: rgba(92,200,164,0.15)'
                : 'background: rgba(138,180,255,0.07)'"
            >
              <!-- MCP — stacked-circle spark -->
              <svg v-if="s.icon === 'mcp'" viewBox="0 0 20 20" fill="none" style="width:18px;height:18px">
                <circle cx="10" cy="10" r="2" fill="#5cc8a4" />
                <circle cx="10" cy="10" r="5" stroke="#5cc8a4" stroke-width="1.2" stroke-opacity="0.6" />
                <circle cx="10" cy="10" r="8" stroke="#5cc8a4" stroke-width="1" stroke-opacity="0.25" />
              </svg>
              <!-- GitHub -->
              <svg v-if="s.icon === 'github'" viewBox="0 0 20 20" fill="none" style="width:18px;height:18px">
                <path fill-rule="evenodd" clip-rule="evenodd" d="M10 2C5.58 2 2 5.58 2 10c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38v-1.34c-2.22.48-2.69-1.07-2.69-1.07-.36-.92-.89-1.17-.89-1.17-.73-.5.05-.49.05-.49.8.06 1.22.82 1.22.82.71 1.22 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.69 7.69 0 0 1 10 6.84c.68 0 1.36.09 2 .26 1.52-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48v2.19c0 .21.15.46.55.38A8.013 8.013 0 0 0 18 10c0-4.42-3.58-8-8-8Z" fill="#8ba1bd"/>
              </svg>
              <!-- Manual / plus -->
              <svg v-if="s.icon === 'manual'" viewBox="0 0 20 20" fill="none" style="width:18px;height:18px">
                <path d="M10 5v10M5 10h10" stroke="#8ba1bd" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </div>

            <!-- Tag -->
            <p class="font-mono text-[10px] uppercase tracking-[0.12em] mb-2"
              :style="i === 0 ? 'color: #5cc8a4' : 'color: #5e7088'"
            >
              {{ s.tag }}
            </p>
            <h4 class="font-semibold mb-2"
              style="font-size: 14px; color: #ffffff; letter-spacing: -0.01em; line-height: 1.3"
            >
              {{ s.title }}
            </h4>
            <p class="leading-relaxed" style="font-size: 12px; color: #8ba1bd; line-height: 1.6">
              {{ s.body }}
            </p>

            <!-- Code snippet on card 1 — the Claude conversation example -->
            <div v-if="i === 0"
              class="mt-5 rounded-md p-3 font-mono"
              style="background: rgba(7,11,16,0.6); border: 1px solid rgba(92,200,164,0.15); font-size: 11px; line-height: 1.5"
            >
              <p style="color: #5e7088">you:</p>
              <p style="color: #cfd4dc" class="mb-2">&ldquo;let&rsquo;s build a tool that <br>turns TikToks into blog posts&rdquo;</p>
              <p style="color: #5e7088">claude:</p>
              <p style="color: #5cc8a4">✓ spawned clipscribe →</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ─── Session in action: terminal mockup ───────────────────────────── -->
    <section class="relative py-16 md:py-28 px-6 overflow-hidden">
      <div class="max-w-5xl mx-auto relative z-10">
        <div class="text-center mb-12">
          <p class="font-mono text-[11px] uppercase tracking-[0.15em] mb-3" style="color: #5cc8a4">
            A session, in the real
          </p>
          <h2 class="font-semibold leading-tight"
            style="font-size: clamp(1.6rem, 3vw, 2.4rem); letter-spacing: -0.03em; color: #ffffff">
            This is what shipping with Vibecell looks like
          </h2>
        </div>

        <!-- Terminal-ish pane -->
        <div
          class="rounded-xl overflow-hidden"
          style="background: rgba(7,11,16,0.72); border: 1px solid rgba(138,180,255,0.12); backdrop-filter: blur(8px); box-shadow: 0 20px 60px rgba(0,0,0,0.35)"
        >
          <!-- Chrome bar -->
          <div class="flex items-center justify-between px-4 py-2.5 border-b"
            style="border-color: rgba(138,180,255,0.08); background: rgba(20,33,50,0.4)">
            <div class="flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full" style="background: #ff6b6b"></span>
              <span class="w-2.5 h-2.5 rounded-full" style="background: #f5b84a"></span>
              <span class="w-2.5 h-2.5 rounded-full" style="background: #5cc8a4"></span>
            </div>
            <span class="font-mono text-[10px] tracking-widest" style="color: #5e7088">
              claude code · vibecell mcp
            </span>
            <span class="font-mono text-[10px]" style="color: #5e7088">⌥⌘K</span>
          </div>

          <!-- Body -->
          <div class="p-6 md:p-8 font-mono text-[12.5px] space-y-4"
            style="line-height: 1.65; color: #cfd4dc">

            <!-- user message -->
            <div>
              <p class="mb-1" style="color: #5e7088">&gt; you</p>
              <p>lass uns ein tool bauen das tiktok clips zu blog posts
                macht. name: <span style="color:#5cc8a4">clipscribe</span></p>
            </div>

            <!-- tool call 1 -->
            <div class="pl-4 border-l-2" style="border-color: rgba(92,200,164,0.3)">
              <p style="color: #5cc8a4">● vibecell_create_project</p>
              <p class="ml-3" style="color: #8ba1bd">
                {<br>
                &nbsp;&nbsp;name: <span style="color:#ffc56b">"Clipscribe"</span>,<br>
                &nbsp;&nbsp;pitch: <span style="color:#ffc56b">"TikTok clips → long-form blog posts with AI"</span>,<br>
                &nbsp;&nbsp;stack: [python, fastapi, whisper, vue-3, openai],<br>
                &nbsp;&nbsp;tags: [ai, content-tool, saas]<br>
                }
              </p>
              <p class="mt-2" style="color: #5cc8a4">
                → https://vibecell.dev/p/clipscribe &nbsp;·&nbsp; pre-filled
                <span style="color:#b592ff">5 stack items</span>,
                <span style="color:#b592ff">3 tags</span>,
                active project = clipscribe
              </p>
            </div>

            <!-- assistant response -->
            <div>
              <p class="mb-1" style="color: #5e7088">● claude</p>
              <p>
                Created <span style="color: #5cc8a4">clipscribe</span> ✓
                I&rsquo;ll start with the FastAPI scaffold + a Whisper
                endpoint. Logging 4 todos &hellip;
              </p>
            </div>

            <!-- tool call 2 -->
            <div class="pl-4 border-l-2" style="border-color: rgba(181,146,255,0.3)">
              <p style="color: #b592ff">● vibecell_todo_batch_add</p>
              <p class="ml-3" style="color: #8ba1bd">
                batch: <span style="color:#ffc56b">"clipscribe-v0"</span>,
                titles: [
                  <span style="color:#ffc56b">"scaffold fastapi"</span>,
                  <span style="color:#ffc56b">"whisper transcribe endpoint"</span>,
                  <span style="color:#ffc56b">"blog-post generator"</span>,
                  <span style="color:#ffc56b">"vue frontend"</span>
                ]
              </p>
              <p class="mt-2" style="color: #b592ff">→ 4 todos visible on dashboard, Claude ticks as it ships</p>
            </div>

            <!-- cursor tick animation hint -->
            <div class="flex items-center gap-2 pt-2" style="color: #5e7088">
              <span>&gt; _</span>
              <span class="inline-block w-1.5 h-3.5 animate-pulse" style="background: #5cc8a4"></span>
              <span class="ml-3 text-[11px]">live &middot; 0 manual clicks</span>
            </div>
          </div>
        </div>

        <!-- Closer line -->
        <p class="text-center mt-10 max-w-xl mx-auto leading-relaxed"
          style="font-size: 13px; color: #8ba1bd">
          No switching to the dashboard, no forms, no copy-paste.
          <span style="color:#cfd4dc">The project exists before the conversation even ends.</span>
        </p>
      </div>
    </section>

    <!-- ─── How it works ─────────────────────────────────────────────────── -->
    <section id="how-it-works" class="py-16 md:py-28 px-6"
      style="background: rgba(20,33,50,0.25); border-top: 1px solid rgba(138,180,255,0.07); border-bottom: 1px solid rgba(138,180,255,0.07)">
      <div class="max-w-5xl mx-auto">
        <div class="text-center mb-16">
          <p class="font-mono text-[11px] uppercase tracking-[0.15em] mb-3" style="color: #5cc8a4">
            Setup in 3 steps
          </p>
          <h2 class="font-semibold" style="font-size: clamp(1.6rem, 3vw, 2.4rem); letter-spacing: -0.03em; color: #ffffff">
            Zero install. Full power.
          </h2>
        </div>

        <div class="grid md:grid-cols-3 gap-8 relative">
          <!-- Connector line (desktop) -->
          <div class="hidden md:block absolute top-8 left-[calc(33.33%+1rem)] right-[calc(33.33%+1rem)] h-px"
            style="background: linear-gradient(90deg, rgba(92,200,164,0.3), rgba(92,200,164,0.3))" />

          <div v-for="step in steps" :key="step.num" class="relative text-center">
            <!-- Number bubble -->
            <div class="w-16 h-16 rounded-full mx-auto mb-6 flex items-center justify-center font-mono font-bold relative"
              style="background: rgba(92,200,164,0.08); border: 1px solid rgba(92,200,164,0.25); color: #5cc8a4; font-size: 18px; box-shadow: 0 0 20px rgba(92,200,164,0.08)">
              {{ step.num }}
              <!-- glow ring pulse -->
              <div class="absolute inset-0 rounded-full animate-ping opacity-10"
                style="background: rgba(92,200,164,0.3); animation-duration: 3s" />
            </div>
            <h3 class="font-semibold mb-3" style="font-size: 15px; color: #ffffff; letter-spacing: -0.01em">
              {{ step.title }}
            </h3>
            <p style="font-size: 12px; color: #8ba1bd; line-height: 1.65">
              {{ step.body }}
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- ─── Pricing teaser ───────────────────────────────────────────────── -->
    <section class="py-16 md:py-28 px-6">
      <div class="max-w-2xl mx-auto">
        <div class="text-center mb-10">
          <p class="font-mono text-[10px] uppercase tracking-[0.18em] mb-3" style="color: #5cc8a4">
            // pricing
          </p>
          <h2 class="font-semibold mb-3" style="font-size: clamp(1.6rem, 3vw, 2.4rem); letter-spacing: -0.03em; color: #ffffff">
            One plan, two cycles.
          </h2>
          <p style="color: #8ba1bd; font-size: 13px; line-height: 1.6">
            7-day trial on monthly · annual locks the price · cancel from the Stripe portal.
          </p>
        </div>

        <!-- Launch marker — thin amber strip, mono-label tradition,
             no emoji, no multi-stop gradient. Mirrors /pricing exactly. -->
        <div
          v-if="launch.active"
          class="rounded-md px-4 py-2.5 mb-5 font-mono flex items-baseline justify-between gap-3"
          style="background: rgba(245,184,74,0.06); border: 1px solid rgba(245,184,74,0.22)"
        >
          <span style="font-size: 10px; color: #f5b84a; letter-spacing: 0.12em; text-transform: uppercase">
            // launch · {{ String(launch.max - launch.remaining).padStart(3, '0') }}/{{ launch.max }}
          </span>
          <span style="font-size: 11px; color: #8ba1bd">
            first {{ launch.remaining }} get <strong style="color:#f5b84a; font-weight: 600">€69.99</strong> · then €99.99
          </span>
        </div>

        <div class="grid md:grid-cols-2 gap-5">
          <!-- Monthly -->
          <div class="rounded-lg p-7 flex flex-col"
            style="background: rgba(20,33,50,0.45); border: 1px solid rgba(138,180,255,0.1)">
            <p class="font-mono text-[10px] uppercase tracking-[0.14em] mb-4" style="color: #5e7088">// pro · monthly</p>
            <div class="flex items-baseline gap-1.5 mb-1">
              <p class="font-bold" style="font-size: 2.6rem; color: #ffffff; letter-spacing: -0.04em; line-height: 1">€8.99</p>
              <p style="color: #8ba1bd; font-size: 12px">/ month</p>
            </div>
            <p class="mb-6 font-mono" style="font-size: 11px; color: #5e7088">7-day trial · no card to start</p>
            <ul class="space-y-1.5 mb-7 flex-1" style="font-size: 12px; color: #8ba1bd">
              <li class="flex gap-2 items-start"><span style="color:#5cc8a4">·</span> Unlimited projects</li>
              <li class="flex gap-2 items-start"><span style="color:#5cc8a4">·</span> AI enrichment from any GitHub repo</li>
              <li class="flex gap-2 items-start"><span style="color:#5cc8a4">·</span> MCP server access</li>
              <li class="flex gap-2 items-start"><span style="color:#5cc8a4">·</span> Auto-cron + workspace secrets</li>
            </ul>
            <button
              class="w-full py-2.5 rounded-md font-mono text-[11px] tracking-wider uppercase transition-opacity hover:opacity-100"
              style="border: 1px solid rgba(138,180,255,0.18); color: #cfd4dc; opacity: 0.85"
              @click="goSignIn">
              Start trial →
            </button>
          </div>

          <!-- Annual / Launch — single accent (amber if launch, mint if standard) -->
          <div class="rounded-lg p-7 flex flex-col relative"
            :style="{
              background: launch.active ? 'rgba(245,184,74,0.04)' : 'rgba(92,200,164,0.04)',
              border: '1px solid ' + (launch.active ? 'rgba(245,184,74,0.28)' : 'rgba(92,200,164,0.28)'),
            }">
            <p class="font-mono text-[10px] uppercase tracking-[0.14em] mb-4"
              :style="{ color: launch.active ? '#f5b84a' : '#5cc8a4' }">
              // pro · annual
            </p>
            <div class="flex items-baseline gap-2 mb-1 flex-wrap">
              <p class="font-bold" :style="{
                fontSize: '2.6rem',
                color: launch.active ? '#f5b84a' : '#ffffff',
                letterSpacing: '-0.04em',
                lineHeight: 1,
              }">{{ launch.active ? '€69.99' : '€99.99' }}</p>
              <p style="color: #8ba1bd; font-size: 12px">/ year</p>
              <!-- Strikethrough €99.99 as a typographic footnote, not a sibling -->
              <p v-if="launch.active" class="font-mono ml-1" style="font-size: 11px; color: #5e7088; text-decoration: line-through; text-decoration-thickness: 1px">
                €99.99
              </p>
            </div>
            <p v-if="launch.active" class="mb-6 font-mono" style="font-size: 10px; color: #f5b84a; letter-spacing: 0.12em; text-transform: uppercase">
              // first 100 only · renews €99.99
            </p>
            <p v-else class="mb-6 font-mono" style="font-size: 11px; color: #5e7088">
              ~7% off vs monthly · billed yearly
            </p>
            <ul class="space-y-1.5 mb-7 flex-1" style="font-size: 12px; color: #8ba1bd">
              <li class="flex gap-2 items-start"><span style="color:#5cc8a4">·</span> Everything in monthly</li>
              <li class="flex gap-2 items-start"><span style="color:#5cc8a4">·</span> Price locked for 12 months</li>
              <li class="flex gap-2 items-start"><span style="color:#5cc8a4">·</span> Stripe Tax — EU-VAT invoicing</li>
              <li class="flex gap-2 items-start"><span style="color:#5cc8a4">·</span> 14-day Widerruf, then committed</li>
            </ul>
            <button
              class="w-full py-2.5 rounded-md font-mono font-semibold text-[11px] tracking-wider uppercase transition-opacity hover:opacity-90"
              :style="{
                background: launch.active ? '#f5b84a' : '#5cc8a4',
                color: '#070b10',
              }"
              @click="goSignIn">
              {{ launch.active ? 'Take launch price →' : 'Get annual →' }}
            </button>
          </div>
        </div>

        <div class="text-center mt-8">
          <router-link to="/pricing"
            class="font-mono transition-colors hover:text-fg-primary"
            style="font-size: 11px; color: #5e7088; letter-spacing: 0.04em">
            full pricing details + FAQ →
          </router-link>
        </div>
      </div>
    </section>

    <!-- ─── Final CTA ────────────────────────────────────────────────────── -->
    <section class="py-20 md:py-32 px-6 text-center relative overflow-hidden"
      style="background: rgba(20,33,50,0.4); border-top: 1px solid rgba(138,180,255,0.07)">
      <!-- Background glow -->
      <div class="absolute inset-0 pointer-events-none"
        style="background: radial-gradient(ellipse 60% 60% at 50% 50%, rgba(92,200,164,0.05) 0%, transparent 70%)" />

      <div class="relative z-10 max-w-2xl mx-auto">
        <p class="font-mono text-[11px] uppercase tracking-[0.15em] mb-4" style="color: #5cc8a4">
          Ready to ship smarter?
        </p>
        <h2 class="font-semibold mb-5" style="font-size: clamp(1.8rem, 4vw, 3rem); letter-spacing: -0.04em; color: #ffffff; line-height: 1.1">
          Start shipping smarter.<br>
          <span style="color: #5cc8a4">Today.</span>
        </h2>
        <p class="mb-10" style="font-size: 14px; color: #8ba1bd; line-height: 1.65">
          Join the builders who never lose project context again.<br>
          7-day trial. No card to start. €8.99/mo after.
        </p>
        <button
          class="px-10 py-4 rounded-xl font-mono font-semibold text-[14px] transition-all hover:opacity-90 hover:scale-[1.02] active:scale-[0.99]"
          style="background: #5cc8a4; color: #070b10; box-shadow: 0 0 40px rgba(92,200,164,0.3), 0 4px 20px rgba(0,0,0,0.3)"
          @click="goSignIn">
          {{ auth.isAuthed ? 'Open dashboard →' : 'Start 7-day trial →' }}
        </button>
        <p class="mt-4 font-mono" style="font-size: 11px; color: #5e7088">
          vibecell.dev · No install · GDPR compliant · Cancel anytime
        </p>
      </div>
    </section>

    <!-- ─── Footer ───────────────────────────────────────────────────────── -->
    <footer class="px-6 py-10" style="border-top: 1px solid rgba(138,180,255,0.08)">
      <div class="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
        <!-- Logo -->
        <div class="flex items-center gap-2.5">
          <span class="font-mono" style="font-size: 20px; color: #5cc8a4">◈</span>
          <span class="font-mono text-[11px] tracking-[0.15em] uppercase" style="color: #5e7088">Vibecell</span>
        </div>
        <!-- Links -->
        <nav class="flex flex-wrap justify-center gap-6" style="font-size: 12px; color: #5e7088">
          <router-link to="/pricing" class="hover:text-fg-muted transition-colors">Pricing</router-link>
          <router-link to="/legal?tab=imprint" class="hover:text-fg-muted transition-colors">Imprint</router-link>
          <router-link to="/legal?tab=privacy" class="hover:text-fg-muted transition-colors">Privacy</router-link>
          <router-link to="/legal?tab=terms" class="hover:text-fg-muted transition-colors">Terms</router-link>
          <a href="https://github.com/lennystepn-hue/vibecell" target="_blank" rel="noopener" class="hover:text-fg-muted transition-colors">GitHub</a>
          <a href="mailto:hello@vibecell.dev" class="hover:text-fg-muted transition-colors">Contact</a>
        </nav>
        <!-- Copyright -->
        <p class="font-mono" style="font-size: 11px; color: #5e7088">© 2026 Vibecell</p>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* Aurora text — sweeps a wide gradient through the text to match the
 * conic-gradient on HeroOrb. 18s linear infinite mirrors the orb's
 * aurora-rotate so headline + orb feel like one breathing organism. */
.aurora-text {
  background-image: linear-gradient(
    100deg,
    #5cc8a4 0%,
    #b592ff 25%,
    #7dffd4 50%,
    #ff6b9d 75%,
    #5cc8a4 100%
  );
  background-size: 300% 100%;
  background-position: 0% 50%;
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
  animation: aurora-shift 18s linear infinite;
  will-change: background-position;
}

@keyframes aurora-shift {
  from { background-position: 0% 50%; }
  to   { background-position: 300% 50%; }
}

/* Reduced-motion users: snapshot the gradient at a calm position, no animation. */
@media (prefers-reduced-motion: reduce) {
  .aurora-text {
    animation: none;
    background-position: 25% 50%;
  }
}
</style>
