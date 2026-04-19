<script setup lang="ts">
import TopBar from "./TopBar.vue";
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <TopBar />
    <main class="flex-1 min-h-0 overflow-hidden">
      <slot />
    </main>
  </div>
</template>
