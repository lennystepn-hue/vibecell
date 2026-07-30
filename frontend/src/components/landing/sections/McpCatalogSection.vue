<script setup lang="ts">
import { useMcpToolCount } from "@/composables/useMcpToolCount";
import ProjectOrb from "@/components/ui/ProjectOrb.vue";

const { count: toolCount } = useMcpToolCount();

/**
 * Capability buckets. Counts are shares of the live total rather than fixed
 * numbers: the previous version hardcoded them with a comment telling the
 * next person to re-bucket by hand whenever a tool was added, and that went
 * stale the first time it happened.
 */
const mcpGroups = [
  {
    seed: "mcp-spawn",
    tag: "Spawn",
    share: 3 / 49,
    blurb: "Describe an idea in Claude — a project appears in the dashboard with stack, tags, pitch pre-filled.",
    signature: "vibecell_create_project",
    accent: true,
  },
  {
    seed: "mcp-read",
    tag: "Read",
    share: 12 / 49,
    blurb: "Claude pulls the full project aggregate, the AI primer, search history, generates resurrection briefs.",
    signature: "vibecell_active",
  },
  {
    seed: "mcp-write",
    tag: "Write",
    share: 20 / 49,
    blurb: "Every session, decision, ship, URL or script Claude touches lands as a one-line tool call.",
    signature: "vibecell_log_session",
  },
  {
    seed: "mcp-todos",
    tag: "Todos",
    share: 6 / 49,
    blurb: "Plan work as visible batches. Claude ticks each one off with a commit note as it ships.",
    signature: "vibecell_todo_batch_add",
  },
  {
    seed: "mcp-secrets",
    tag: "Secrets",
    share: 4 / 49,
    blurb: "Workspace-scoped vault. References to 1Password / Bitwarden, or inline-encrypted with a DEK.",
    signature: "vibecell_secret_get_value",
  },
  {
    seed: "mcp-onboard",
    tag: "Setup",
    share: 4 / 49,
    blurb: "One line wires up every MCP client on the machine, then Claude reads your repos and fills the portfolio.",
    signature: "vibecell_onboard",
  },
];

/** Round each bucket off the live total so the shares still add up. */
function countFor(share: number): number {
  return Math.max(1, Math.round(share * toolCount.value));
}
</script>

<template>
<!-- ─── MCP-native: tool catalog ─────────────────────────────────────── -->
<section class="relative py-16 md:py-28 px-6 overflow-hidden">
  <!-- Ambient fabric: terminal-green wash with mesh -->
  <div class="absolute inset-0 pointer-events-none"
    style="background:
      radial-gradient(ellipse 60% 40% at 50% 20%, rgb(var(--signal-green-rgb) / 0.07) 0%, transparent 70%),
      radial-gradient(ellipse 40% 50% at 20% 80%, rgb(var(--border-rgb) / 0.05) 0%, transparent 70%)" />

  <div class="relative z-10 max-w-6xl mx-auto">
    <!-- Heading block -->
    <div class="text-center mb-4">
      <p class="font-mono text-micro uppercase tracking-caps mb-3" style="color: var(--signal-green)">
        <span class="w-1.5 h-1.5 rounded-full bg-signal-green inline-block mr-2 align-middle animate-pulse" />
        MCP-native, not MCP-compatible
      </p>
      <h2 class="font-semibold leading-tight mb-4"
        style="font-size: clamp(1.8rem, 3.5vw, 2.6rem); letter-spacing: -0.03em; color: var(--fg-primary)">
        {{ toolCount }} tools. One mental model.<br>
        <span style="color: var(--fg-muted)">Claude drives everything.</span>
      </h2>
      <p class="max-w-2xl mx-auto leading-relaxed"
        style="font-size: 14px; color: var(--fg-muted); line-height: 1.7">
        Vibecell isn&rsquo;t an app that happens to talk MCP. It&rsquo;s a set of {{ toolCount }} typed
        tool endpoints that Claude (or Cursor, or Zed) can wire itself into in under 10 seconds.
        Every capability in the dashboard &mdash; creating projects, logging sessions, tracking
        drift, managing secrets &mdash; is a first-class tool call.
      </p>
    </div>

    <!-- Tool-group list: 6 rows, each with orb + meta + blurb + signature tool.
         Horizontal stripe layout (not cards) to DIFFERENTIATE from the
         card patterns used elsewhere on the page. Reads like a reference
         index — dense, scannable, calm. -->
    <div class="mt-16 divide-y" style="border-color: var(--border-subtle); border-top: 1px solid var(--border-subtle); border-bottom: 1px solid var(--border-subtle)">
      <!-- Mobile layout: orb + (tag/count + signature pill) on row 1,
           blurb hidden. Desktop: original 4-col grid with rigid 160px
           middle column + 1fr blurb. The grid-cols only kicks in at md;
           below that we use flex-wrap so nothing overflows. -->
      <div
        v-for="g in mcpGroups"
        :key="g.tag"
        class="flex flex-wrap items-center gap-x-4 gap-y-2 py-5 px-2 transition-colors hover:bg-white/[0.02]
               md:grid md:grid-cols-[auto_160px_1fr_auto] md:gap-6"
        style="border-top: 1px solid var(--border-subtle)"
      >
        <!-- Orb — the category identity -->
        <ProjectOrb :seed="g.seed" :size="44" />

        <!-- Tag + count — flex-1 on mobile so it pushes the pill to
             the right edge; auto on desktop because the grid handles it. -->
        <div class="flex-1 md:flex-none min-w-0">
          <p class="font-semibold truncate"
            style="font-size: 15px; color: var(--fg-primary); letter-spacing: -0.01em">
            {{ g.tag }}
          </p>
          <p class="font-mono tabular-nums mt-0.5"
            :style="g.accent
              ? 'font-size: 11px; color: var(--signal-green)'
              : 'font-size: 11px; color: var(--fg-subtle)'">
            {{ countFor(g.share) }} tools
          </p>
        </div>

        <!-- Blurb — only shown md+ to keep mobile rows compact. -->
        <p class="hidden md:block leading-relaxed"
          style="font-size: 13px; color: var(--fg-muted); line-height: 1.55">
          {{ g.blurb }}
        </p>

        <!-- Signature tool name. order-last on mobile keeps it on the
             same first row as the tag block; on desktop the grid puts
             it at the far right anyway. -->
        <span
          class="font-mono text-micro px-2.5 py-1 rounded-md whitespace-nowrap tabular-nums shrink-0"
          :style="g.accent
            ? 'background: rgb(var(--signal-green-rgb) / 0.08); color: var(--signal-green); border: 1px solid rgb(var(--signal-green-rgb) / 0.18)'
            : 'background: rgb(var(--scrim-rgb) / 0.5); color: var(--fg-muted); border: 1px solid rgb(var(--border-rgb) / 0.1)'"
        >
          {{ g.signature }}
        </span>
      </div>
    </div>

    <!-- Footnote strip -->
    <div class="mt-12 flex flex-wrap items-center justify-center gap-4 sm:gap-8 font-mono text-micro"
      style="color: var(--fg-subtle)">
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
</template>
