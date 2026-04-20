<script setup lang="ts">
import { onMounted, ref } from "vue";

import ProjectCard from "@/components/projects/ProjectCard.vue";
import QuickAddProject from "@/components/projects/QuickAddProject.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useProjectsStore } from "@/stores/projects";

const projects = useProjectsStore();
const quickAddOpen = ref(false);

onMounted(() => projects.fetchList());
</script>

<template>
  <div class="max-w-[1200px] mx-auto px-6 py-8">
    <header class="flex items-baseline justify-between mb-8">
      <div>
        <h1 class="text-display text-fg-primary tracking-tight">Projects</h1>
        <p class="text-fg-muted mt-1">
          <span class="tabular-nums">{{ projects.list.length }}</span>
          {{ projects.list.length === 1 ? "project" : "projects" }} in your workspace
        </p>
      </div>
      <div class="flex gap-2">
        <RouterLink
          to="/import/github"
          class="inline-flex h-10 items-center gap-2 rounded-md px-4 font-medium text-body border border-border bg-bg-surface/50 text-fg-body hover:bg-bg-surface-hi transition-colors"
        >
          <span aria-hidden="true">↗</span>
          <span>Import from GitHub</span>
        </RouterLink>
        <PrimaryButton @click="quickAddOpen = true">
          <span aria-hidden="true">+</span>
          <span>New project</span>
        </PrimaryButton>
      </div>
    </header>

    <div v-if="projects.loadingList && projects.list.length === 0" class="text-fg-muted">
      <p class="mono-label">loading your projects…</p>
    </div>

    <EmptyState
      v-else-if="projects.list.length === 0"
      title="Your workspace is empty."
      subtitle="Pull in your repos from GitHub or add the first one manually — either works."
    >
      <template #actions>
        <RouterLink
          to="/import/github"
          class="inline-flex h-10 items-center gap-2 rounded-md px-4 font-medium text-body border border-border bg-bg-surface/50 text-fg-body hover:bg-bg-surface-hi transition-colors"
        >
          Import from GitHub
        </RouterLink>
        <PrimaryButton @click="quickAddOpen = true">+ New project</PrimaryButton>
      </template>
    </EmptyState>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <ProjectCard v-for="p in projects.list" :key="p.id" :project="p" />
    </div>

    <QuickAddProject :open="quickAddOpen" @close="quickAddOpen = false" />
  </div>
</template>
