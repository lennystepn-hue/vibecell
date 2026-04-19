<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import ProjectTelemetryRail from "@/components/app/ProjectTelemetryRail.vue";
import SidebarProjects from "@/components/app/SidebarProjects.vue";
import ProjectContextEditor from "@/components/projects/ProjectContextEditor.vue";
import ProjectFocusCard from "@/components/projects/ProjectFocusCard.vue";
import ProjectInfraCard from "@/components/projects/ProjectInfraCard.vue";
import ProjectDecisionsCard from "@/components/projects/ProjectDecisionsCard.vue";
import ProjectLaunchesCard from "@/components/projects/ProjectLaunchesCard.vue";
import ProjectLinksCommands from "@/components/projects/ProjectLinksCommands.vue";
import ProjectNotesCard from "@/components/projects/ProjectNotesCard.vue";
import ProjectSessionsCard from "@/components/projects/ProjectSessionsCard.vue";
import ShipButton from "@/components/projects/ShipButton.vue";
import ProjectStackEditor from "@/components/projects/ProjectStackEditor.vue";
import ProjectStatusDropdown from "@/components/projects/ProjectStatusDropdown.vue";
import ProjectTagsEditor from "@/components/projects/ProjectTagsEditor.vue";
import { api } from "@/api/client";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";

const route = useRoute();
const router = useRouter();
const projects = useProjectsStore();
const toast = useToastStore();

const editingContext = ref(false);
const confirmingDelete = ref(false);
const deleting = ref(false);

function load(slug: string) {
  return projects.fetchProject(slug);
}

async function doDelete() {
  const project = projects.active;
  if (!project) return;
  deleting.value = true;
  const { error } = await api.DELETE("/api/v1/projects/{slug}", {
    params: { path: { slug: project.slug } },
  });
  deleting.value = false;
  if (error) {
    toast.push("Couldn't delete project", "error");
    return;
  }
  toast.push(`${project.name} deleted`, "success");
  projects.active = null;
  await projects.fetchList();
  router.push("/p");
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
      confirmingDelete.value = false;
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
          <div v-if="!editingContext" class="flex flex-col items-end gap-2 self-start">
            <ShipButton :project="projects.active" />
            <button
              type="button"
              class="mono-label hover:text-fg-body transition-colors"
              @click="editingContext = true"
            >✎ edit context</button>
            <button
              type="button"
              class="mono-label transition-colors"
              :class="confirmingDelete ? 'text-signal-red' : 'hover:text-signal-red text-fg-subtle'"
              @click="confirmingDelete = true"
            >🗑 delete project</button>
          </div>
        </header>

        <!-- Delete confirmation banner -->
        <div
          v-if="confirmingDelete"
          class="mb-6 rounded-lg p-4 flex items-center gap-4"
          :style="{ background: 'var(--signal-red-bg)', border: '1px solid var(--signal-red)' }"
        >
          <div class="flex-1">
            <p class="text-section text-signal-red font-semibold">Delete this project?</p>
            <p class="text-small text-fg-muted mt-1">
              Removes <span class="font-mono">{{ projects.active.slug }}</span>
              and all its children (repos, envs, links, commands, stack, tags, context).
              This cannot be undone.
            </p>
          </div>
          <button
            type="button"
            class="h-9 px-4 rounded-md font-medium text-small text-fg-body hover:text-fg-primary transition-colors"
            :disabled="deleting"
            @click="confirmingDelete = false"
          >Cancel</button>
          <button
            type="button"
            class="h-9 px-4 rounded-md font-semibold text-small"
            :style="{ background: 'var(--signal-red)', color: 'var(--bg-body-to)' }"
            :disabled="deleting"
            @click="doDelete"
          >{{ deleting ? "Deleting…" : "Yes, delete" }}</button>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <div class="xl:col-span-2">
            <ProjectContextEditor
              v-if="editingContext"
              :project="projects.active"
              @close="editingContext = false"
            />
            <ProjectFocusCard v-else :project="projects.active" />
          </div>
          <ProjectStackEditor :project="projects.active" />
          <div class="xl:col-span-2">
            <ProjectInfraCard :project="projects.active" />
          </div>
          <ProjectTagsEditor :project="projects.active" />
          <div class="xl:col-span-3">
            <ProjectLinksCommands :project="projects.active" />
          </div>
          <div class="xl:col-span-3">
            <ProjectSessionsCard :project="projects.active" />
          </div>
          <div class="xl:col-span-3">
            <ProjectDecisionsCard :project="projects.active" />
          </div>
          <div class="xl:col-span-3">
            <ProjectLaunchesCard :project="projects.active" />
          </div>
          <div class="xl:col-span-3">
            <ProjectNotesCard :project="projects.active" />
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
