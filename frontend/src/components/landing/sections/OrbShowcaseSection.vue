<script setup lang="ts">
import { useMcpToolCount } from "@/composables/useMcpToolCount";
import ProjectOrb from "@/components/ui/ProjectOrb.vue";

const { count: toolCount } = useMcpToolCount();

/**
 * Each orb illustrates one capability. The seed doubles as the hash key for
 * ProjectOrb, so colours stay stable across the page.
 */
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
    blurb: `${toolCount.value} typed endpoints Claude can drive — create, log, ship, search.`,
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
</script>

<template>
<!-- ─── Orb feature storytelling ─────────────────────────────────────── -->
<section class="relative py-16 md:py-28 px-6 overflow-hidden">
  <!-- Subtle radial glow behind the orbs — same aesthetic as the hero -->
  <div class="absolute inset-0 pointer-events-none"
    style="background: radial-gradient(ellipse 70% 50% at 50% 40%, rgb(var(--border-rgb) / 0.06) 0%, transparent 70%)" />
  <div
    class="absolute top-1/3 left-1/4 w-[500px] h-[500px] rounded-full pointer-events-none"
    style="background: radial-gradient(circle, rgb(var(--signal-violet-rgb) / 0.05) 0%, transparent 70%); filter: blur(40px)"
  />
  <div
    class="absolute top-1/2 right-1/4 w-[500px] h-[500px] rounded-full pointer-events-none"
    style="background: radial-gradient(circle, rgb(var(--signal-green-rgb) / 0.05) 0%, transparent 70%); filter: blur(40px)"
  />

  <div class="relative z-10 max-w-6xl mx-auto">
    <!-- Heading -->
    <div class="text-center mb-16">
      <p class="font-mono text-micro uppercase tracking-caps mb-3" style="color: var(--signal-green)">
        Eight things that just happen
      </p>
      <h2 class="font-semibold leading-tight mb-4"
        style="font-size: clamp(1.6rem, 3vw, 2.4rem); letter-spacing: -0.03em; color: var(--fg-primary)">
        One orb, one superpower.<br>
        <span style="color: var(--fg-muted)">All of them on by default.</span>
      </h2>
      <p class="max-w-xl mx-auto leading-relaxed" style="font-size: 14px; color: var(--fg-muted)">
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
        <span class="font-mono text-micro tracking-wide mt-1"
          style="color: var(--fg-body); letter-spacing: 0.03em">
          {{ o.label }}
        </span>
        <p class="max-w-[180px] leading-snug"
          style="font-size: 11.5px; color: var(--fg-muted); line-height: 1.55">
          {{ o.blurb }}
        </p>
      </div>
    </div>

    <!-- Spawn paths — three sub-sections -->
    <div class="text-center mb-10">
      <p class="font-mono text-micro uppercase tracking-caps mb-3" style="color: var(--signal-green)">
        Three ways to spawn a project
      </p>
      <h3 class="font-semibold"
        style="font-size: clamp(1.3rem, 2.4vw, 1.8rem); letter-spacing: -0.02em; color: var(--fg-primary)">
        Start from a conversation, a repo, or a blank slate
      </h3>
    </div>

    <div class="grid md:grid-cols-3 gap-5">
      <div
        v-for="(s, i) in spawnPaths"
        :key="s.tag"
        class="rounded-xl p-6 transition-all duration-300 hover:-translate-y-[2px]"
        :style="i === 0
          ? 'background: rgb(var(--signal-green-rgb) / 0.06); border: 1px solid rgb(var(--signal-green-rgb) / 0.2); box-shadow: 0 0 32px rgb(var(--signal-green-rgb) / 0.04)'
          : 'background: var(--bg-surface); border: 1px solid rgb(var(--border-rgb) / 0.1)'"
      >
        <!-- Icon tile -->
        <div class="w-10 h-10 rounded-lg flex items-center justify-center mb-5"
          :style="i === 0
            ? 'background: rgb(var(--signal-green-rgb) / 0.15)'
            : 'background: rgb(var(--border-rgb) / 0.07)'"
        >
          <!-- MCP — stacked-circle spark -->
          <svg v-if="s.icon === 'mcp'" viewBox="0 0 20 20" fill="none" style="width:18px;height:18px">
            <circle cx="10" cy="10" r="2" fill="var(--signal-green)" />
            <circle cx="10" cy="10" r="5" stroke="var(--signal-green)" stroke-width="1.2" stroke-opacity="0.6" />
            <circle cx="10" cy="10" r="8" stroke="var(--signal-green)" stroke-width="1" stroke-opacity="0.25" />
          </svg>
          <!-- GitHub -->
          <svg v-if="s.icon === 'github'" viewBox="0 0 20 20" fill="none" style="width:18px;height:18px">
            <path fill-rule="evenodd" clip-rule="evenodd" d="M10 2C5.58 2 2 5.58 2 10c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38v-1.34c-2.22.48-2.69-1.07-2.69-1.07-.36-.92-.89-1.17-.89-1.17-.73-.5.05-.49.05-.49.8.06 1.22.82 1.22.82.71 1.22 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.69 7.69 0 0 1 10 6.84c.68 0 1.36.09 2 .26 1.52-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48v2.19c0 .21.15.46.55.38A8.013 8.013 0 0 0 18 10c0-4.42-3.58-8-8-8Z" fill="var(--fg-muted)"/>
          </svg>
          <!-- Manual / plus -->
          <svg v-if="s.icon === 'manual'" viewBox="0 0 20 20" fill="none" style="width:18px;height:18px">
            <path d="M10 5v10M5 10h10" stroke="var(--fg-muted)" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>

        <!-- Tag -->
        <p class="font-mono text-nano uppercase tracking-caps mb-2"
          :style="i === 0 ? 'color: var(--signal-green)' : 'color: var(--fg-subtle)'"
        >
          {{ s.tag }}
        </p>
        <h4 class="font-semibold mb-2"
          style="font-size: 14px; color: var(--fg-primary); letter-spacing: -0.01em; line-height: 1.3"
        >
          {{ s.title }}
        </h4>
        <p class="leading-relaxed" style="font-size: 12px; color: var(--fg-muted); line-height: 1.6">
          {{ s.body }}
        </p>

        <!-- Code snippet on card 1 — the Claude conversation example -->
        <div v-if="i === 0"
          class="mt-5 rounded-md p-3 font-mono"
          style="background: rgb(var(--scrim-rgb) / 0.6); border: 1px solid rgb(var(--signal-green-rgb) / 0.15); font-size: 11px; line-height: 1.5"
        >
          <p style="color: var(--fg-subtle)">you:</p>
          <p style="color: var(--fg-body)" class="mb-2">&ldquo;let&rsquo;s build a tool that <br>turns TikToks into blog posts&rdquo;</p>
          <p style="color: var(--fg-subtle)">claude:</p>
          <p style="color: var(--signal-green)">✓ spawned clipscribe →</p>
        </div>
      </div>
    </div>
  </div>
</section>
</template>
