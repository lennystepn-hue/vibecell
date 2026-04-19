<script setup lang="ts">
interface Props {
  tone: "green" | "amber" | "red" | "blue" | "muted";
  glow?: boolean;
}
const props = withDefaults(defineProps<Props>(), { glow: true });

const toneClass = {
  green: "bg-signal-green text-signal-green",
  amber: "bg-signal-amber text-signal-amber",
  red: "bg-signal-red text-signal-red",
  blue: "bg-signal-blue text-signal-blue",
  muted: "bg-fg-subtle text-fg-subtle",
}[props.tone];
</script>

<template>
  <span
    :class="['inline-block w-1.5 h-1.5 rounded-full', toneClass]"
    :style="glow ? 'box-shadow: 0 0 6px currentColor' : ''"
    aria-hidden="true"
  />
</template>
