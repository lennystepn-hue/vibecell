<script setup lang="ts">
import { computed } from "vue";

import { usePresenceStore } from "@/stores/presence";

const props = withDefaults(defineProps<{
  slug: string;
  /** "dot" = bare pulsing green dot. "pill" = dot + "claude · tool_name" label. */
  variant?: "dot" | "pill";
  /** Compact mode — smaller dot for sidebar. */
  dense?: boolean;
}>(), {
  variant: "dot",
  dense: false,
});

const presence = usePresenceStore();
const live = computed(() => presence.isLive(props.slug));
const tool = computed(() => presence.toolFor(props.slug));
const age = computed(() => presence.ageFor(props.slug));

function friendlyTool(raw: string | null): string {
  if (!raw) return "claude";
  // "vibecell.secret_get_value" → "secret_get_value"
  return raw.replace(/^vibecell[._]/, "").replace(/_/g, "_");
}

function ageLabel(s: number | null): string {
  if (s === null) return "";
  if (s < 5) return "now";
  if (s < 60) return `${s}s ago`;
  return `${Math.floor(s / 60)}m ago`;
}
</script>

<template>
  <span v-if="live" class="inline-flex items-center gap-1.5 align-middle" :title="`Claude is live · ${tool ?? ''} · ${ageLabel(age)}`">
    <!-- Pulsing green dot -->
    <span class="relative inline-flex" :class="dense ? 'w-1.5 h-1.5' : 'w-2 h-2'" aria-hidden="true">
      <span class="absolute inset-0 rounded-full bg-signal-green opacity-75 animate-ping" />
      <span class="relative inline-flex w-full h-full rounded-full bg-signal-green" style="box-shadow: 0 0 8px rgba(92,200,164,0.6)" />
    </span>
    <span v-if="variant === 'pill'" class="font-mono text-[10px] uppercase tracking-[0.1em] text-signal-green whitespace-nowrap">
      claude · {{ friendlyTool(tool) }}
    </span>
  </span>
</template>
