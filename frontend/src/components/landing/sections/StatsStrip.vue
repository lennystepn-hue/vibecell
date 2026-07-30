<script setup lang="ts">
import { onMounted, ref } from "vue";

import { useMcpToolCount } from "@/composables/useMcpToolCount";

const { count: toolCount } = useMcpToolCount();

/**
 * Count-up on first paint. Targets are read live where possible — the tool
 * count used to be hardcoded here, in the MCP catalogue heading, and in an
 * orb blurb, with a comment instructing the next person to keep all three in
 * sync by hand. That instruction failed the first time a tool was added.
 */
const counters = ref([
  { value: 0, target: 0, label: "MCP tools", suffix: "", live: true },
  { value: 0, target: 5, label: "IDE clients", suffix: "" },
  { value: 0, target: 2, label: "setup", suffix: "s" },
  { value: 0, target: 0, label: "install", suffix: "" },
]);

onMounted(() => {
  const duration = 1400;
  const start = Date.now();
  function tick() {
    const progress = Math.min((Date.now() - start) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    counters.value.forEach((c) => {
      const target = c.live ? toolCount.value : c.target;
      c.value = Math.round(ease * target);
    });
    if (progress < 1) setTimeout(tick, 16);
  }
  setTimeout(tick, 400);
});
</script>

<template>
<!-- ─── Stats strip ──────────────────────────────────────────────────── -->
<div class="border-y" style="border-color: var(--border-subtle); background: rgb(var(--bg-surface-rgb) / 0.3)">
  <div class="max-w-4xl mx-auto px-6 py-8 grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
    <div v-for="c in counters" :key="c.label">
      <p class="font-mono font-bold mb-1" style="font-size: 2rem; color: var(--signal-green); letter-spacing: -0.04em">
        {{ c.value }}{{ c.suffix }}
      </p>
      <p class="font-mono text-micro uppercase tracking-caps" style="color: var(--fg-subtle)">
        {{ c.label }}
      </p>
    </div>
  </div>
</div>
</template>
