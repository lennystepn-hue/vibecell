<script setup lang="ts">
defineProps<{ label: string }>();
</script>

<template>
  <div
    class="px-4 pt-3 pb-1 mono-label"
    style="border-top: 1px solid var(--border-subtle)"
  >
    {{ label }}
  </div>
</template>
