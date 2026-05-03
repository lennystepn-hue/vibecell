<script setup lang="ts">
/**
 * Public /install page — anonymous-accessible, single-purpose: hand the
 * user a copy-paste prompt that wires Vibecell into whatever AI editor
 * they're using.
 *
 * The whole pitch fits on one screen: "Paste this into Claude/Cursor/Zed.
 * Done." No tabs, no per-editor branching, no OAuth drama. The AI runs
 * the installer, opens OAuth in the user's browser, and reads the SKILL
 * doc on its own.
 *
 * Why public/anonymous: the URL is shareable. "Just paste vibecell.dev/install
 * into your AI" beats any landing-page tour. Bookmark-friendly. Tweet-friendly.
 */
import { ref } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useRouteMeta } from "@/composables/useMeta";
import { INSTALL_PROMPT_PITCH, VIBECELL_INSTALL_PROMPT } from "@/lib/installPrompt";

useRouteMeta({
  title: "Install — Vibecell · paste one prompt, AI installs itself",
  description:
    "Skip the settings dance. Paste one prompt into Claude Code, Claude Desktop, Cursor, Zed — the AI installs the Vibecell MCP, runs OAuth, reads the operating manual, and reports back. ~10 seconds.",
  canonical: "https://vibecell.dev/install",
});

const copied = ref(false);

async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(VIBECELL_INSTALL_PROMPT);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2400);
  } catch {
    /* clipboard denied — user can still select-all manually */
  }
}
</script>

<template>
  <div class="min-h-[calc(100vh-44px)] px-6 py-12">
    <div class="w-full max-w-[680px] mx-auto">
      <!-- Brand -->
      <div class="flex items-center justify-between mb-10">
        <div class="flex items-center gap-2 text-fg-subtle">
          <span class="text-signal-green font-mono text-section">◈</span>
          <span class="font-mono text-small tracking-[0.08em] uppercase">Vibecell · install</span>
        </div>
        <a
          href="/"
          class="font-mono text-small text-fg-subtle hover:text-fg-body transition-colors"
        >← back to vibecell.dev</a>
      </div>

      <!-- Hero -->
      <header class="mb-8">
        <MonoLabel>10-second install</MonoLabel>
        <h1 class="text-display text-fg-primary tracking-tight mt-3">
          Let the AI install itself.
        </h1>
        <p class="text-body text-fg-muted mt-3 max-w-xl">
          {{ INSTALL_PROMPT_PITCH }}
        </p>
      </header>

      <!-- Prompt block -->
      <section
        class="rounded-lg p-5 mb-5"
        style="background: rgba(20,33,50,0.5); border: 1px solid rgba(138,180,255,0.12)"
      >
        <header class="flex items-center justify-between mb-3 select-none">
          <MonoLabel>prompt</MonoLabel>
          <span class="font-mono text-[10px] text-fg-subtle">
            ~{{ Math.ceil(VIBECELL_INSTALL_PROMPT.length / 4) }} tokens
          </span>
        </header>
        <pre class="font-mono text-[12px] leading-relaxed whitespace-pre-wrap select-all text-fg-body">{{ VIBECELL_INSTALL_PROMPT }}</pre>
      </section>

      <PrimaryButton size="lg" class="w-full mb-6" @click="copyPrompt">
        {{ copied ? "✓ Copied — paste into your AI" : "Copy prompt" }}
      </PrimaryButton>

      <!-- 3-step explainer -->
      <section class="grid grid-cols-3 gap-3 mb-8">
        <div
          class="rounded-md p-4"
          style="background: var(--bg-elevated); border: 1px solid var(--border)"
        >
          <span class="font-mono text-section text-signal-green leading-none" aria-hidden="true">01</span>
          <p class="text-small text-fg-primary font-medium mt-2">Copy</p>
          <p class="text-[11px] text-fg-muted mt-1">One click. No fields, no signup yet.</p>
        </div>
        <div
          class="rounded-md p-4"
          style="background: var(--bg-elevated); border: 1px solid var(--border)"
        >
          <span class="font-mono text-section text-signal-green leading-none" aria-hidden="true">02</span>
          <p class="text-small text-fg-primary font-medium mt-2">Paste</p>
          <p class="text-[11px] text-fg-muted mt-1">Into Claude Code, Claude Desktop, Cursor, Zed — anything that speaks MCP.</p>
        </div>
        <div
          class="rounded-md p-4"
          style="background: var(--bg-elevated); border: 1px solid var(--border)"
        >
          <span class="font-mono text-section text-signal-green leading-none" aria-hidden="true">03</span>
          <p class="text-small text-fg-primary font-medium mt-2">Confirm</p>
          <p class="text-[11px] text-fg-muted mt-1">OAuth pops in your browser. Approve. The AI takes over from there.</p>
        </div>
      </section>

      <!-- Manual fallbacks -->
      <section
        class="rounded-md p-4"
        style="background: var(--bg-elevated); border: 1px solid var(--border)"
      >
        <MonoLabel>prefer to do it by hand?</MonoLabel>
        <ul class="mt-3 space-y-1.5 text-small text-fg-body">
          <li>
            <span class="text-fg-subtle font-mono mr-2">→</span>
            Claude Code:
            <code class="font-mono text-[11px] text-fg-body">claude mcp add vibecell https://vibecell.dev/mcp --transport http --scope user</code>
          </li>
          <li>
            <span class="text-fg-subtle font-mono mr-2">→</span>
            Claude Desktop:
            <a
              href="claude://add-connector?url=https%3A%2F%2Fvibecell.dev"
              class="link"
            >one-click add connector</a>
          </li>
          <li>
            <span class="text-fg-subtle font-mono mr-2">→</span>
            Cursor / Zed / Windsurf: paste
            <code class="font-mono text-[11px] text-fg-body">https://vibecell.dev/mcp</code>
            into the editor's MCP settings
          </li>
        </ul>
      </section>

      <p class="text-center font-mono text-[10px] text-fg-subtle mt-8">
        // 7-day trial · €8.99/mo · LAUNCH69 €69.99/yr (first 100)
      </p>
    </div>
  </div>
</template>
