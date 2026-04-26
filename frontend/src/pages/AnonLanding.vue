<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import HeroOrb from "@/components/landing/HeroOrb.vue";
import DashboardPreview from "@/components/landing/DashboardPreview.vue";
import UserMenu from "@/components/app/UserMenu.vue";
import ProjectOrb from "@/components/ui/ProjectOrb.vue";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

function goSignIn() {
  router.push(auth.isAuthed ? "/p" : "/login");
}

function goDashboard() {
  router.push("/p");
}

function scrollToDemo() {
  document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" });
}

// Animated counter for stat strip
const counters = ref([
  { value: 0, target: 38, label: "MCP tools", suffix: "" },
  { value: 0, target: 5, label: "IDE clients", suffix: "" },
  { value: 0, target: 2, label: "setup", suffix: "s" },
  { value: 0, target: 0, label: "install", suffix: "" },
]);

// MCP tool catalog — 6 capability cards. Seeded so every category gets
// its own orb (consistent visual language with the rest of the page).
// One sentence of plain English + a single signature tool name.
const mcpGroups = [
  {
    seed: "mcp-spawn",
    tag: "Spawn",
    count: 4,
    blurb: "Describe an idea in Claude — a project appears in the dashboard with stack, tags, pitch pre-filled.",
    signature: "vibecell_create_project",
    accent: true,
  },
  {
    seed: "mcp-read",
    tag: "Read",
    count: 11,
    blurb: "Claude pulls the full project aggregate, searches your history, generates a resurrection brief.",
    signature: "vibecell_active",
  },
  {
    seed: "mcp-write",
    tag: "Write",
    count: 13,
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
    blurb: "38 typed endpoints Claude can drive — create, log, ship, search.",
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

    <!-- ─── Nav ──────────────────────────────────────────────────────────── -->
    <header class="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-3"
      style="background: rgba(7,11,16,0.75); backdrop-filter: blur(12px); border-bottom: 1px solid rgba(138,180,255,0.08)">
      <div class="flex items-center gap-2.5">
        <span class="text-signal-green font-mono text-[18px] leading-none select-none">◈</span>
        <span class="font-mono text-[11px] tracking-[0.15em] uppercase text-fg-subtle">Vibecell</span>
      </div>
      <nav class="hidden sm:flex items-center gap-6">
        <router-link to="/pricing"
          class="text-small text-fg-muted hover:text-fg-primary transition-colors duration-150">
          Pricing
        </router-link>
        <router-link to="/legal"
          class="text-small text-fg-muted hover:text-fg-primary transition-colors duration-150">
          Legal
        </router-link>
        <a href="https://github.com/lennystepn-hue/vibecell" target="_blank" rel="noopener"
          class="text-small text-fg-muted hover:text-fg-primary transition-colors duration-150">
          GitHub
        </a>
      </nav>
      <div class="flex items-center gap-3">
        <UserMenu v-if="auth.isAuthed" variant="light" />
        <button
          v-if="auth.isAuthed"
          class="px-4 py-1.5 rounded text-small font-mono bg-signal-green hover:opacity-90 transition-opacity"
          style="color: #070b10"
          @click="goDashboard">
          Open dashboard →
        </button>
        <button
          v-else
          class="px-4 py-1.5 rounded text-small font-mono bg-signal-green hover:opacity-90 transition-opacity"
          style="color: #070b10"
          @click="goSignIn">
          Get started →
        </button>
      </div>
    </header>

    <!-- ─── Hero ─────────────────────────────────────────────────────────── -->
    <section class="relative flex items-center overflow-hidden pt-20 pb-12 min-h-[88vh]">
      <!-- Subtle grid background -->
      <div class="absolute inset-0 pointer-events-none"
        style="background-image: linear-gradient(rgba(138,180,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(138,180,255,0.03) 1px, transparent 1px); background-size: 60px 60px" />
      <!-- Orb-palette gradient blooms — soft violet + mint + pink washes that
           tie the hero bg into the orb's own colors. -->
      <div class="absolute -top-40 -left-40 w-[780px] h-[780px] rounded-full pointer-events-none"
        style="background: radial-gradient(circle, rgba(181,146,255,0.10) 0%, transparent 65%); filter: blur(20px)" />
      <div class="absolute top-1/3 right-[-20%] w-[700px] h-[700px] rounded-full pointer-events-none"
        style="background: radial-gradient(circle, rgba(92,200,164,0.09) 0%, transparent 65%); filter: blur(20px)" />
      <div class="absolute bottom-0 left-1/2 -translate-x-1/2 w-[900px] h-[400px] rounded-full pointer-events-none"
        style="background: radial-gradient(ellipse, rgba(255,107,157,0.06) 0%, transparent 70%); filter: blur(30px)" />

      <div class="relative z-10 w-full max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-12 items-center py-20">

        <!-- Left: copy — ruthlessly trimmed. H1 + one-line subhead + CTAs. -->
        <div>
          <h1 class="font-sans font-semibold mb-6 leading-[1.04] tracking-tight"
            style="font-size: clamp(2.6rem, 5.5vw, 4.4rem); letter-spacing: -0.04em; color: #ffffff">
            The project console<br>
            for
            <!-- Single accent picked from the orb palette — keeps brand link
                 to the rotating sphere on the right without the multi-stop
                 rainbow that read AI-ish. -->
            <span style="color: #5cc8a4">shipping devs.</span>
          </h1>

          <p class="mb-9 leading-relaxed max-w-md"
            style="font-size: 1.05rem; color: #cfd4dc; line-height: 1.55">
            One source of truth for every weekend hack, side-project,
            and full app — with an MCP server your AI already speaks.
          </p>

          <div class="flex flex-wrap gap-3 mb-7">
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

          <!-- Feature signal — surfaces the actual product surface
               (dashboard + MCP tools + cron + secrets + history) rather
               than infrastructure. Mono-label cadence, no marketing copy. -->
          <p class="font-mono text-[11px]" style="color: #5e7088; letter-spacing: 0.04em">
            dashboard · 47 MCP tools · auto-cron · session log · workspace secrets
          </p>
        </div>

        <!-- Right: Hero orb — slowly-rotating aurora-glass sphere. Carries
             the same visual language as the per-project orbs used throughout
             the dashboard, scaled up and animated. -->
        <div class="relative flex items-center justify-center">
          <div class="relative w-full" style="aspect-ratio: 1; max-width: 520px; margin: auto">
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
          <!-- Claude (Anthropic 4-point star) -->
          <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: #cfd4dc; font-size: 14px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 2 L13.5 10.5 L22 12 L13.5 13.5 L12 22 L10.5 13.5 L2 12 L10.5 10.5 Z"/>
            </svg>
            <span class="font-mono text-[13px]">Claude</span>
          </span>
          <!-- Cursor (curl icon) -->
          <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: #cfd4dc; font-size: 14px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path d="M4 4 L20 12 L4 20 L12 12 Z" fill="currentColor" fill-opacity="0.2"/>
              <path d="M4 4 L20 12 L4 20 L12 12 Z"/>
            </svg>
            <span class="font-mono text-[13px]">Cursor</span>
          </span>
          <!-- OpenAI (hex flower) -->
          <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: #cfd4dc; font-size: 14px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
              <circle cx="12" cy="8" r="3.5"/>
              <circle cx="7.2" cy="14.5" r="3.5"/>
              <circle cx="16.8" cy="14.5" r="3.5"/>
            </svg>
            <span class="font-mono text-[13px]">OpenAI</span>
          </span>
          <!-- Zed (stylised Z) -->
          <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: #cfd4dc; font-size: 14px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path d="M5 6 H19 L5 18 H19" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span class="font-mono text-[13px]">Zed</span>
          </span>
          <!-- Continue -->
          <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: #cfd4dc; font-size: 14px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path d="M6 4 L18 12 L6 20" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M2 4 L14 12 L2 20" stroke-linecap="round" stroke-linejoin="round" stroke-opacity="0.45"/>
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
    <section class="relative py-28 px-6 overflow-hidden">
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
            38 tools. One mental model.<br>
            <span style="color: #8ba1bd">Claude drives everything.</span>
          </h2>
          <p class="max-w-2xl mx-auto leading-relaxed"
            style="font-size: 14px; color: #8ba1bd; line-height: 1.7">
            Vibecell isn&rsquo;t an app that happens to talk MCP. It&rsquo;s a set of 38 typed tool
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
          <div
            v-for="g in mcpGroups"
            :key="g.tag"
            class="grid grid-cols-[auto_160px_1fr_auto] items-center gap-6 py-5 px-2 transition-colors hover:bg-white/[0.02]"
            style="border-top: 1px solid rgba(138,180,255,0.08)"
          >
            <!-- Orb — the category identity -->
            <ProjectOrb :seed="g.seed" :size="44" />

            <!-- Tag + count -->
            <div>
              <p class="font-semibold"
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

            <!-- Blurb -->
            <p class="leading-relaxed hidden md:block"
              style="font-size: 13px; color: #8ba1bd; line-height: 1.55">
              {{ g.blurb }}
            </p>

            <!-- Signature tool name -->
            <span
              class="font-mono text-[11px] px-2.5 py-1 rounded-md whitespace-nowrap tabular-nums"
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
    <section class="relative py-28 px-6 overflow-hidden">
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
    <section class="relative py-28 px-6 overflow-hidden">
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
    <section id="how-it-works" class="py-28 px-6"
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
    <section class="py-28 px-6">
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
    <section class="py-32 px-6 text-center relative overflow-hidden"
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
          Free forever. No credit card.
        </p>
        <button
          class="px-10 py-4 rounded-xl font-mono font-semibold text-[14px] transition-all hover:opacity-90 hover:scale-[1.02] active:scale-[0.99]"
          style="background: #5cc8a4; color: #070b10; box-shadow: 0 0 40px rgba(92,200,164,0.3), 0 4px 20px rgba(0,0,0,0.3)"
          @click="goSignIn">
          {{ auth.isAuthed ? 'Open dashboard →' : 'Get started — free →' }}
        </button>
        <p class="mt-4 font-mono" style="font-size: 11px; color: #5e7088">
          vibecell.dev · No install · Free plan · GDPR compliant
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
          <router-link to="/legal" class="hover:text-fg-muted transition-colors">Privacy</router-link>
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
