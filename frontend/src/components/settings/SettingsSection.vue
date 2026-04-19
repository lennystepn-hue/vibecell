<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>();
</script>

<template>
  <section class="glass rounded-lg p-6 mb-5">
    <header class="mb-5">
      <h2 class="text-section text-fg-primary tracking-tight">{{ title }}</h2>
      <p v-if="subtitle" class="text-small text-fg-muted mt-1">{{ subtitle }}</p>
    </header>
    <slot />
  </section>
</template>
