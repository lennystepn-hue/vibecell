<script setup lang="ts">
import SignalDot from "./SignalDot.vue";

type Status = "idea" | "building" | "live" | "paused" | "shipped" | "archived" | "dead";

interface Props {
  status: Status;
}
const props = defineProps<Props>();

// Distinct visual per status. `live` has an extra pulsing glow so it pops
// vs `building` — both are phosphor-green but `live` reads as "in production".
const mapping: Record<
  Status,
  { tone: "green" | "amber" | "red" | "blue" | "muted"; label: string; pulse?: boolean; bold?: boolean }
> = {
  idea: { tone: "muted", label: "idea" },
  building: { tone: "green", label: "building" },
  live: { tone: "green", label: "live", pulse: true, bold: true },
  paused: { tone: "amber", label: "paused" },
  shipped: { tone: "blue", label: "shipped" },
  archived: { tone: "muted", label: "archived" },
  dead: { tone: "red", label: "dead" },
};

const bgVar: Record<string, string> = {
  green: "var(--signal-green-bg)",
  amber: "var(--signal-amber-bg)",
  red: "var(--signal-red-bg)",
  blue: "var(--signal-blue-bg)",
  muted: "transparent",
};

const colorVar: Record<string, string> = {
  green: "var(--signal-green)",
  amber: "var(--signal-amber)",
  red: "var(--signal-red)",
  blue: "var(--signal-blue)",
  muted: "var(--fg-muted)",
};

const cfg = mapping[props.status];
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
    <SignalDot v-if="cfg.tone !== 'muted'" :tone="cfg.tone" :glow="cfg.pulse" />
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
