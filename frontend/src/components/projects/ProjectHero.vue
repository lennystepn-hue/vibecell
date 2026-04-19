<script setup lang="ts">
import StatusPill from "@/components/ui/StatusPill.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
defineProps<{ project: Project }>();
</script>

<template>
  <div class="flex items-start gap-4 mb-6">
    <span class="text-[44px] leading-none" aria-hidden="true">{{ project.emoji || "📦" }}</span>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-3 flex-wrap">
        <h1 class="text-display text-fg-primary tracking-tight">{{ project.name }}</h1>
        <StatusPill :status="project.status as never" />
      </div>
      <p v-if="project.pitch" class="text-body text-fg-muted mt-2 max-w-3xl">{{ project.pitch }}</p>
      <p v-else class="mono-label mt-2 opacity-50">// no pitch set</p>
    </div>
  </div>
</template>
