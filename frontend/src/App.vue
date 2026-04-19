<script setup lang="ts">
import AppLayout from "@/components/app/AppLayout.vue";
import CommandPalette from "@/components/palette/CommandPalette.vue";
</script>

<template>
  <AppLayout>
    <RouterView />
  </AppLayout>
  <CommandPalette />
</template>
