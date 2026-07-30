<script setup lang="ts">
/**
 * What actually happens now, which is not what this said before.
 *
 * Step 2 used to read "Copy one config line into your
 * claude_desktop_config.json". That was true of the old manual path and
 * became wrong the day `hangar setup` shipped: nobody edits that file by
 * hand any more, and the one-liner configures every MCP client on the
 * machine rather than one.
 */
const steps = [
  {
    num: "01",
    title: "Create your workspace",
    body: "Magic-link, passkey or Google. Ready in under 10 seconds — no card for the trial.",
  },
  {
    num: "02",
    title: "Run one line",
    body: "Copy it from the dashboard, paste it into a terminal. It pairs the machine and wires up every AI editor it finds — Claude Code, Claude Desktop, Cursor, Windsurf, Zed.",
  },
  {
    num: "03",
    title: "Watch it fill itself in",
    body: "Claude reads your repos and writes the pitch, stack and status for each one while you watch. Then context follows you across projects, machines and clients.",
  },
];
</script>

<template>
<!-- ─── How it works ─────────────────────────────────────────────────── -->
<section id="how-it-works" class="py-16 md:py-28 px-6"
  style="background: rgb(var(--bg-surface-rgb) / 0.25); border-top: 1px solid rgb(var(--border-rgb) / 0.07); border-bottom: 1px solid rgb(var(--border-rgb) / 0.07)">
  <div class="max-w-5xl mx-auto">
    <div class="text-center mb-16">
      <p class="font-mono text-micro uppercase tracking-caps mb-3" style="color: var(--signal-green)">
        Setup in 3 steps
      </p>
      <h2 class="font-semibold" style="font-size: clamp(1.6rem, 3vw, 2.4rem); letter-spacing: -0.03em; color: var(--fg-primary)">
        Zero install. Full power.
      </h2>
    </div>

    <div class="grid md:grid-cols-3 gap-8 relative">
      <!-- Connector line (desktop) -->
      <div class="hidden md:block absolute top-8 left-[calc(33.33%+1rem)] right-[calc(33.33%+1rem)] h-px"
        style="background: linear-gradient(90deg, rgb(var(--signal-green-rgb) / 0.3), rgb(var(--signal-green-rgb) / 0.3))" />

      <div v-for="step in steps" :key="step.num" class="relative text-center">
        <!-- Number bubble -->
        <div class="w-16 h-16 rounded-full mx-auto mb-6 flex items-center justify-center font-mono font-bold relative"
          style="background: rgb(var(--signal-green-rgb) / 0.08); border: 1px solid rgb(var(--signal-green-rgb) / 0.25); color: var(--signal-green); font-size: 18px; box-shadow: 0 0 20px rgb(var(--signal-green-rgb) / 0.08)">
          {{ step.num }}
          <!-- glow ring pulse -->
          <div class="absolute inset-0 rounded-full animate-ping opacity-10"
            style="background: rgb(var(--signal-green-rgb) / 0.3); animation-duration: 3s" />
        </div>
        <h3 class="font-semibold mb-3" style="font-size: 15px; color: var(--fg-primary); letter-spacing: -0.01em">
          {{ step.title }}
        </h3>
        <p style="font-size: 12px; color: var(--fg-muted); line-height: 1.65">
          {{ step.body }}
        </p>
      </div>
    </div>
  </div>
</section>
</template>
