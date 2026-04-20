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
    class="group block glass rounded-lg p-4 transition-all duration-fast ease-out hover:bg-bg-surface-hi hover:border-border-strong relative"
  >
    <a
      v-if="project.github_url"
      :href="project.github_url"
      target="_blank"
      rel="noopener noreferrer"
      class="absolute top-3 right-3 text-fg-subtle hover:text-fg-body transition-colors z-10"
      aria-label="Open on GitHub"
      @click.stop
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>
      </svg>
    </a>
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
