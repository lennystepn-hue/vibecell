<script setup lang="ts">
import { RouterLink, useRoute } from "vue-router";

const route = useRoute();

const items = [
  { path: "/settings", label: "account" },
  { path: "/settings/integrations", label: "integrations" },
  { path: "/settings/connections", label: "connections" },
];
</script>

<template>
  <nav class="chrome border-r w-[180px] shrink-0 flex flex-col h-full">
    <div class="mono-label px-3 pt-3 pb-2">settings</div>
    <div class="flex-1 overflow-y-auto px-1">
      <RouterLink
        v-for="i in items"
        :key="i.path"
        :to="i.path"
        :class="[
          'block px-3 py-2 rounded-md mono text-small',
          'transition-colors duration-fast ease-out',
          route.path === i.path
            ? 'bg-bg-surface-hi text-fg-primary'
            : 'text-fg-muted hover:bg-bg-surface/60 hover:text-fg-body',
        ]"
      >
        {{ i.label }}
      </RouterLink>
    </div>
  </nav>
</template>
