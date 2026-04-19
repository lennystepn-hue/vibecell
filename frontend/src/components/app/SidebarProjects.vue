<script setup lang="ts">
import { onMounted } from "vue";
import { RouterLink, useRoute } from "vue-router";

import SignalDot from "@/components/ui/SignalDot.vue";
import { useProjectsStore } from "@/stores/projects";

const route = useRoute();
const projects = useProjectsStore();

onMounted(() => {
  if (projects.list.length === 0) {
    projects.fetchList();
  }
});

const toneFor = (status: string) => {
  switch (status) {
    case "building":
    case "live":
      return "green";
    case "paused":
      return "amber";
    case "shipped":
      return "blue";
    case "dead":
      return "red";
    default:
      return "muted";
  }
};
</script>

<template>
  <aside class="chrome border-r w-[200px] shrink-0 flex flex-col h-full">
    <div class="mono-label px-3 pt-3 pb-2 flex items-center gap-2">
      <span class="tabular-nums">{{ projects.list.length }}</span>
      <span>projects</span>
    </div>
    <div class="flex-1 overflow-y-auto px-1">
      <RouterLink
        v-for="p in projects.list"
        :key="p.id"
        :to="`/p/${p.slug}`"
        :class="[
          'group flex items-center gap-2 px-2 py-1.5 rounded-md mb-0.5',
          'font-mono text-small',
          'transition-colors duration-fast ease-out',
          route.params.slug === p.slug
            ? 'bg-bg-surface-hi text-fg-primary'
            : 'text-fg-muted hover:bg-bg-surface/60 hover:text-fg-body',
        ]"
      >
        <span
          class="text-[14px] leading-none shrink-0 transition-[filter] duration-fast"
          :style="route.params.slug === p.slug ? 'filter: saturate(1)' : 'filter: saturate(0.85)'"
          aria-hidden="true"
        >{{ p.emoji || "📦" }}</span>
        <span class="truncate flex-1">{{ p.slug }}</span>
        <SignalDot :tone="toneFor(p.status)" :glow="false" />
      </RouterLink>
    </div>
    <footer class="border-t border-border-subtle px-3 py-2 mono-label">
      <RouterLink to="/p" class="hover:text-fg-body transition-colors">← all projects</RouterLink>
    </footer>
  </aside>
</template>
