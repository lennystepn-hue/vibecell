<script setup lang="ts">
import SignalDot from "./SignalDot.vue";

type Status = "idea" | "building" | "live" | "paused" | "shipped" | "archived" | "dead";

interface Props {
  status: Status;
}
defineProps<Props>();

const mapping: Record<Status, { tone: "green" | "amber" | "red" | "blue" | "muted"; label: string }> = {
  idea: { tone: "muted", label: "idea" },
  building: { tone: "green", label: "building" },
  live: { tone: "green", label: "live" },
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
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm font-mono text-[10px]"
    :style="{ background: bgVar[mapping[status].tone], color: colorVar[mapping[status].tone] }"
  >
    <SignalDot v-if="mapping[status].tone !== 'muted'" :tone="mapping[status].tone" />
    <span>{{ mapping[status].label }}</span>
  </span>
</template>
