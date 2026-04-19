<script setup lang="ts">
defineProps<{ keys: string }>();
</script>

<template>
  <kbd
    class="font-mono text-[10px] px-1.5 py-0.5 rounded-sm"
    style="background: var(--signal-blue-bg); color: var(--fg-muted); border: 1px solid var(--border-subtle)"
  >{{ keys }}</kbd>
</template>
