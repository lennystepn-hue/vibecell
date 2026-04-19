<script setup lang="ts">
import { onMounted, watch } from "vue";
import { useRoute } from "vue-router";

import ProjectTelemetryRail from "@/components/app/ProjectTelemetryRail.vue";
import SidebarProjects from "@/components/app/SidebarProjects.vue";
import ProjectFocusCard from "@/components/projects/ProjectFocusCard.vue";
import ProjectHero from "@/components/projects/ProjectHero.vue";
import ProjectInfraCard from "@/components/projects/ProjectInfraCard.vue";
import ProjectLinksCommands from "@/components/projects/ProjectLinksCommands.vue";
import ProjectStackCard from "@/components/projects/ProjectStackCard.vue";
import { useProjectsStore } from "@/stores/projects";

const route = useRoute();
const projects = useProjectsStore();

function load(slug: string) {
  return projects.fetchProject(slug);
}

onMounted(() => {
  if (typeof route.params.slug === "string") {
    load(route.params.slug);
  }
});

watch(
  () => route.params.slug,
  (slug) => {
    if (typeof slug === "string") {
      load(slug);
    }
  },
);
</script>

<template>
  <div class="flex h-[calc(100vh-44px)]">
    <SidebarProjects />

    <section class="flex-1 min-w-0 overflow-y-auto">
      <div
        v-if="projects.loadingActive && !projects.active"
        class="flex items-center justify-center h-full text-fg-muted"
      >
        <p class="mono-label">loading project…</p>
      </div>

      <div v-else-if="projects.active" class="max-w-[1100px] px-8 py-8 mx-auto">
        <ProjectHero :project="projects.active" />

        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <div class="xl:col-span-2">
            <ProjectFocusCard :project="projects.active" />
          </div>
          <ProjectStackCard :project="projects.active" />
          <div class="xl:col-span-2">
            <ProjectInfraCard :project="projects.active" />
          </div>
          <div class="xl:col-span-3">
            <ProjectLinksCommands :project="projects.active" />
          </div>
        </div>
      </div>

      <div v-else class="flex items-center justify-center h-full">
        <div class="text-center max-w-sm">
          <h1 class="text-title text-fg-primary">Project not found</h1>
          <p class="text-fg-muted mt-2">
            The slug <code class="font-mono text-fg-body">{{ route.params.slug }}</code>
            doesn't exist in this workspace.
          </p>
          <RouterLink to="/p" class="link text-body mt-4 inline-block">← back to all</RouterLink>
        </div>
      </div>
    </section>

    <ProjectTelemetryRail v-if="projects.active" :project="projects.active" />
  </div>
</template>
