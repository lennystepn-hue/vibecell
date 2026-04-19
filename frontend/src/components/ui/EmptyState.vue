<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>();
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-4 py-16 px-8 text-center">
    <h2 class="font-sans text-title text-fg-primary tracking-tight">{{ title }}</h2>
    <p v-if="subtitle" class="text-fg-muted max-w-sm">{{ subtitle }}</p>
    <div class="flex gap-3 mt-2">
      <slot name="actions" />
    </div>
  </div>
</template>
