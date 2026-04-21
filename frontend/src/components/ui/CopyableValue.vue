<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{
  value: string;
  display?: string;
  mono?: boolean;
  small?: boolean;
}>();

const copied = ref(false);
async function copy() {
  try {
    await navigator.clipboard.writeText(props.value);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1500);
  } catch {}
}
</script>

<template>
  <button
    type="button"
    class="group inline-flex items-center gap-1.5 max-w-full text-left transition-colors hover:text-fg-primary"
    :class="[mono ? 'font-mono' : '', small ? 'text-small' : 'text-body']"
    :title="`Click to copy: ${value}`"
    @click="copy"
  >
    <span class="truncate">{{ display ?? value }}</span>
    <span
      v-if="copied"
      class="shrink-0 text-signal-green text-[10px] font-mono tracking-wider"
    >✓ COPIED</span>
    <svg
      v-else
      class="shrink-0 w-3 h-3 opacity-0 group-hover:opacity-60 transition-opacity text-fg-muted"
      viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"
    >
      <path d="M5 2a1 1 0 0 0-1 1v1H3a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-1h1a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H5zm0 2h8v8h-1V6a2 2 0 0 0-2-2H5V4zM3 6h7v8H3V6z"/>
    </svg>
  </button>
</template>
