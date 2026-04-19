<script setup lang="ts">
import MonoLabel from "@/components/ui/MonoLabel.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
defineProps<{ project: Project }>();
</script>

<template>
  <section class="glass rounded-lg p-5">
    <MonoLabel>stack</MonoLabel>
    <div v-if="project.stack.length > 0" class="flex flex-wrap gap-2 mt-3">
      <span
        v-for="s in project.stack"
        :key="s.stack_item_slug"
        class="inline-flex items-center gap-1.5 px-2.5 h-6 rounded-sm font-mono text-[11px]"
        :style="{
          background: 'var(--signal-blue-bg)',
          color: 'var(--fg-body)',
          border: '1px solid var(--border-subtle)',
        }"
      >
        {{ s.name }}
      </span>
    </div>
    <p v-else class="text-small text-fg-muted italic mt-2">— nothing attached yet —</p>
  </section>
</template>
