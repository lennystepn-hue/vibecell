<script setup lang="ts">
defineProps<{ label: string }>();
</script>

<template>
  <div class="grid grid-cols-[1fr_auto] items-baseline gap-x-2 text-small py-0.5">
    <span class="text-fg-muted">{{ label }}</span>
    <span class="text-fg-body tabular-nums"><slot /></span>
  </div>
</template>
