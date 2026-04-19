<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import ProjectTelemetryRail from "@/components/app/ProjectTelemetryRail.vue";
import SidebarProjects from "@/components/app/SidebarProjects.vue";
import ProjectContextEditor from "@/components/projects/ProjectContextEditor.vue";
import ProjectFocusCard from "@/components/projects/ProjectFocusCard.vue";
import ProjectInfraCard from "@/components/projects/ProjectInfraCard.vue";
import ProjectLinksCommands from "@/components/projects/ProjectLinksCommands.vue";
import ProjectStackCard from "@/components/projects/ProjectStackCard.vue";
import ProjectStatusDropdown from "@/components/projects/ProjectStatusDropdown.vue";
import { useProjectsStore } from "@/stores/projects";

const route = useRoute();
const projects = useProjectsStore();

const editingContext = ref(false);

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
      editingContext.value = false;
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
        <header class="flex items-start gap-4 mb-6">
          <span class="text-[44px] leading-none" aria-hidden="true">
            {{ projects.active.emoji || "📦" }}
          </span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-3 flex-wrap">
              <h1 class="text-display text-fg-primary tracking-tight">{{ projects.active.name }}</h1>
              <ProjectStatusDropdown :project="projects.active" />
            </div>
            <p v-if="projects.active.pitch" class="text-body text-fg-muted mt-2 max-w-3xl">
              {{ projects.active.pitch }}
            </p>
            <p v-else class="mono-label mt-2 opacity-50">// no pitch set</p>
          </div>
          <button
            v-if="!editingContext"
            type="button"
            class="mono-label hover:text-fg-body transition-colors self-start"
            @click="editingContext = true"
          >✎ edit context</button>
        </header>

        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <div class="xl:col-span-2">
            <ProjectContextEditor
              v-if="editingContext"
              :project="projects.active"
              @close="editingContext = false"
            />
            <ProjectFocusCard v-else :project="projects.active" />
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
