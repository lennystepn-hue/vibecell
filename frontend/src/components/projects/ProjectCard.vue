<script setup lang="ts">
import { RouterLink } from "vue-router";

import StatusPill from "@/components/ui/StatusPill.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectListItem"];

defineProps<{ project: Project }>();
</script>

<template>
  <RouterLink
    :to="`/p/${project.slug}`"
    class="group block glass rounded-lg p-4 transition-all duration-fast ease-out hover:bg-bg-surface-hi hover:border-border-strong"
  >
    <div class="flex items-start gap-3 mb-2">
      <span
        class="text-[28px] leading-none transition-[filter] duration-fast"
        style="filter: saturate(0.85)"
        aria-hidden="true"
      >{{ project.emoji || "📦" }}</span>
      <div class="flex-1 min-w-0">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-section font-semibold text-fg-primary tracking-tight truncate">
            {{ project.name }}
          </h3>
          <StatusPill :status="project.status as never" />
        </div>
        <p class="mono text-small text-fg-subtle truncate mt-0.5">{{ project.slug }}</p>
      </div>
    </div>
    <p v-if="project.pitch" class="text-small text-fg-muted line-clamp-2 mt-3">
      {{ project.pitch }}
    </p>
    <p v-else class="mono-label mt-3 opacity-50">// no pitch yet</p>
  </RouterLink>
</template>

<style scoped>
.group:hover span[aria-hidden="true"] {
  filter: saturate(1) !important;
}
</style>
