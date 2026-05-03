<script setup lang="ts">
/**
 * ProjectPrimerCard — read-only viewer for the project's AI primer.
 *
 * The primer is authored by the AI via the `vibecell_set_primer` MCP tool,
 * fetched by the AI via `vibecell_primer` at session start. The dashboard
 * is intentionally a viewer, not an editor: keeping authoring in the AI's
 * hands is the whole point — the AI watches the codebase evolve, the
 * primer evolves with it, and the user never has to maintain the doc by
 * hand.
 *
 * UI states:
 *   • Empty — explains the contract + a one-line prompt the user can
 *     paste at any AI in their editor to bootstrap the primer.
 *   • Filled — pre-wrap monospace render + Copy button.
 */
import { computed, ref } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import type { components } from "@/api/types.gen";

// ProjectFullOut grew a primer_md field server-side; the generated OpenAPI
// types lag a deploy, so layer the property in by hand.
type Project = components["schemas"]["ProjectFullOut"] & {
  primer_md?: string | null;
};

const props = defineProps<{ project: Project }>();

const justCopied = ref(false);

const primer = computed<string>(() => (props.project.primer_md ?? "").trimEnd());
const hasPrimer = computed(() => primer.value.length > 0);

const BOOTSTRAP_PROMPT = computed(
  () =>
    `Write the project primer for this codebase and save it via the ` +
    `vibecell_set_primer MCP tool. Author it from real evidence — read ` +
    `the codebase, recent commits, decisions, and ships. Cover: what this ` +
    `is, tech stack, where things live, conventions, watch-outs, ` +
    `operations cheatsheet, what "done" looks like. Keep it evergreen, ` +
    `~800-1500 words. Then re-fetch via vibecell_primer to confirm.`,
);

async function copyPrimer() {
  if (!hasPrimer.value) return;
  try {
    await navigator.clipboard.writeText(primer.value);
    justCopied.value = true;
    setTimeout(() => {
      justCopied.value = false;
    }, 1800);
  } catch {
    /* clipboard denied — user can still select-all manually */
  }
}

async function copyBootstrapPrompt() {
  try {
    await navigator.clipboard.writeText(BOOTSTRAP_PROMPT.value);
    justCopied.value = true;
    setTimeout(() => {
      justCopied.value = false;
    }, 1800);
  } catch {
    /* ignore */
  }
}
</script>

<template>
  <section class="glass rounded-lg p-5 flex flex-col h-full min-h-0">
    <header class="flex items-center justify-between mb-3 select-none">
      <h3 class="mono-label text-fg-muted">
        //primer
        <span v-if="hasPrimer" class="opacity-60">({{ primer.length.toLocaleString() }} chars)</span>
      </h3>
      <div class="flex items-center gap-3">
        <span class="mono-label opacity-60">authored by AI</span>
        <button
          v-if="hasPrimer"
          type="button"
          class="mono-label text-fg-muted hover:text-fg-body transition-colors"
          @click="copyPrimer"
        >{{ justCopied ? "✓ copied" : "copy" }}</button>
      </div>
    </header>

    <!-- ── VIEW MODE ────────────────────────────────────────────────── -->
    <div v-if="hasPrimer" class="flex-1 min-h-0 overflow-y-auto">
      <pre
        class="whitespace-pre-wrap break-words font-mono text-small leading-relaxed text-fg-body"
      >{{ primer }}</pre>
    </div>

    <!-- ── EMPTY STATE ──────────────────────────────────────────────── -->
    <div v-else class="flex-1 min-h-0 flex flex-col items-start justify-start gap-3">
      <MonoLabel>// primer not yet authored</MonoLabel>
      <p class="text-small text-fg-muted leading-relaxed max-w-prose">
        The primer is your project's evergreen README aimed at AIs joining
        cold. It's authored and maintained by the AI itself — not by you —
        via the
        <code class="font-mono text-fg-body">vibecell_set_primer</code>
        MCP tool, and read on every session start via
        <code class="font-mono text-fg-body">vibecell_primer</code>. Keeps
        the doc in lockstep with the codebase without you having to
        maintain a thing.
      </p>
      <p class="text-small text-fg-muted leading-relaxed max-w-prose">
        Bootstrap it: paste the prompt below into any AI that has Vibecell
        paired (Claude Code, Cursor, Zed, …). It'll read the codebase, the
        recent commits, your decisions and ships, then write + save the
        primer.
      </p>

      <div
        class="rounded-md p-3 w-full font-mono text-[12px] leading-relaxed whitespace-pre-wrap select-all"
        style="background:rgba(20,33,50,0.5); border:1px solid rgba(138,180,255,0.12); color:var(--fg-body); max-height:180px; overflow-y:auto"
      >{{ BOOTSTRAP_PROMPT }}</div>

      <button
        type="button"
        class="mt-1 inline-flex items-center gap-2 px-4 py-2 rounded-md text-small font-mono"
        :style="{
          background: 'var(--signal-green-bg)',
          color: 'var(--signal-green)',
          border: '1px solid var(--signal-green)',
        }"
        @click="copyBootstrapPrompt"
      >
        <span aria-hidden="true">✦</span>
        <span>{{ justCopied ? "✓ copied — paste at your AI" : "Copy bootstrap prompt" }}</span>
      </button>
    </div>
  </section>
</template>
