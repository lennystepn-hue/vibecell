<script setup lang="ts">
import { computed } from "vue";

import SignalDot from "./SignalDot.vue";

type Status = "idea" | "building" | "live" | "paused" | "shipped" | "archived" | "dead";
type Tone = "green" | "amber" | "red" | "blue" | "muted" | "violet" | "teal";

interface Props {
  status: Status;
}
const props = defineProps<Props>();

// One distinct tone per status so they're all visually unique. `live`
// shares green with building semantically (both are "alive") but gets a
// pulsing glow to differentiate — earlier versions also shared green
// without the pulse, which read as two identical pills.
const mapping: Record<
  Status,
  { tone: Tone; label: string; pulse?: boolean; bold?: boolean }
> = {
  idea: { tone: "violet", label: "idea" },
  building: { tone: "teal", label: "building" },
  live: { tone: "green", label: "live", pulse: true, bold: true },
  paused: { tone: "amber", label: "paused" },
  shipped: { tone: "blue", label: "shipped" },
  archived: { tone: "muted", label: "archived" },
  dead: { tone: "red", label: "dead" },
};

const bgVar: Record<Tone, string> = {
  green: "var(--signal-green-bg)",
  amber: "var(--signal-amber-bg)",
  red: "var(--signal-red-bg)",
  blue: "var(--signal-blue-bg)",
  violet: "var(--signal-violet-bg)",
  teal: "var(--signal-teal-bg)",
  muted: "transparent",
};

const colorVar: Record<Tone, string> = {
  green: "var(--signal-green)",
  amber: "var(--signal-amber)",
  red: "var(--signal-red)",
  blue: "var(--signal-blue)",
  violet: "var(--signal-violet)",
  teal: "var(--signal-teal)",
  muted: "var(--fg-muted)",
};

// MUST be a computed — `const cfg = mapping[props.status]` runs once at
// setup, which means the pill stays stuck on the initial status forever
// even though the prop flows new values in. This was THE bug that made
// status changes look non-functional in the UI.
const cfg = computed(() => mapping[props.status]);
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm font-mono text-[10px]"
    :class="[cfg.bold ? 'font-semibold' : '', cfg.pulse ? 'live-pill' : '']"
    :style="{
      background: bgVar[cfg.tone],
      color: colorVar[cfg.tone],
      boxShadow: cfg.pulse ? `0 0 0 1px ${colorVar[cfg.tone]}, 0 0 10px ${colorVar[cfg.tone]}` : undefined,
    }"
  >
    <!-- Dot always rendered so every status has a consistent indicator. -->
    <SignalDot :tone="cfg.tone" :glow="cfg.pulse" />
    <span>{{ cfg.label }}</span>
  </span>
</template>

<style scoped>
@keyframes live-pulse {
  0%, 100% { box-shadow: 0 0 0 1px var(--signal-green), 0 0 8px rgba(92, 200, 164, 0.6); }
  50%      { box-shadow: 0 0 0 1px var(--signal-green), 0 0 16px rgba(92, 200, 164, 0.9); }
}
.live-pill {
  animation: live-pulse 2s ease-in-out infinite;
}
@media (prefers-reduced-motion: reduce) {
  .live-pill { animation: none; }
}
</style>
