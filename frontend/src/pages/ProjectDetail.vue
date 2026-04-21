<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import LivePulse from "@/components/app/LivePulse.vue";
import ProjectTelemetryRail from "@/components/app/ProjectTelemetryRail.vue";
import SidebarProjects from "@/components/app/SidebarProjects.vue";
import ProjectContextEditor from "@/components/projects/ProjectContextEditor.vue";
import ProjectFocusCard from "@/components/projects/ProjectFocusCard.vue";
import ProjectInfraCard from "@/components/projects/ProjectInfraCard.vue";
import ProjectDecisionsCard from "@/components/projects/ProjectDecisionsCard.vue";
import ProjectEnvironmentsCard from "@/components/projects/ProjectEnvironmentsCard.vue";
import ProjectLaunchesCard from "@/components/projects/ProjectLaunchesCard.vue";
import ProjectLinksCommands from "@/components/projects/ProjectLinksCommands.vue";
import ProjectNotesCard from "@/components/projects/ProjectNotesCard.vue";
import ProjectSessionsCard from "@/components/projects/ProjectSessionsCard.vue";
import ShipButton from "@/components/projects/ShipButton.vue";
import ProjectStackEditor from "@/components/projects/ProjectStackEditor.vue";
import ProjectTagsEditor from "@/components/projects/ProjectTagsEditor.vue";
import ProjectHealthCard from "@/components/projects/ProjectHealthCard.vue";
import ProjectActivityTimeline from "@/components/projects/ProjectActivityTimeline.vue";
import ProjectOverviewChips from "@/components/projects/ProjectOverviewChips.vue";
import ProjectSecretsCard from "@/components/projects/ProjectSecretsCard.vue";
import CopyableValue from "@/components/ui/CopyableValue.vue";
import StatusPill from "@/components/ui/StatusPill.vue";
import { api } from "@/api/client";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";

const route = useRoute();
const router = useRouter();
const projects = useProjectsStore();
const toast = useToastStore();

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function fmtRel(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return fmtDate(iso);
}

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

      <div v-else-if="projects.active" class="max-w-[1400px] px-8 py-8 mx-auto">

        <!-- Hero -->
        <header class="mb-6">
          <div class="flex items-start justify-between gap-6">
            <div class="flex items-start gap-4 min-w-0">
              <span class="text-[44px] leading-none" aria-hidden="true">{{ projects.active.emoji || "📦" }}</span>
              <div class="min-w-0">
                <div class="flex items-baseline gap-3 flex-wrap">
                  <h1 class="text-display text-fg-primary tracking-tight truncate">{{ projects.active.name }}</h1>
                  <StatusPill :status="projects.active.status as never" />
                  <CopyableValue :value="projects.active.slug" mono small class="text-fg-subtle" />
                  <LivePulse :slug="projects.active.slug" variant="pill" />
                </div>
                <p v-if="projects.active.pitch" class="text-body text-fg-muted mt-1 max-w-3xl">{{ projects.active.pitch }}</p>
                <div class="flex items-center gap-3 mt-3 text-small text-fg-subtle flex-wrap">
                  <span v-if="(projects.active as any).created_at" class="mono-label">Created {{ fmtDate((projects.active as any).created_at) }}</span>
                  <span v-if="(projects.active as any).updated_at" class="mono-label">Updated {{ fmtRel((projects.active as any).updated_at) }}</span>
                  <span v-if="(projects.active as any).archived_at" class="mono-label text-signal-amber">Archived</span>
                  <span v-else class="mono-label text-signal-green">Active</span>
                </div>
                <ProjectOverviewChips :slug="projects.active.slug" class="mt-3" />
              </div>
            </div>
            <!-- Top-right actions -->
            <div class="flex items-center gap-2 shrink-0">
              <ShipButton :project="projects.active" />
              <button
                type="button"
                class="mono-label text-fg-muted hover:text-fg-body transition-colors"
                @click="editingContext = true"
              >✎ edit</button>
              <button
                type="button"
                class="mono-label text-fg-muted hover:text-signal-red transition-colors"
                @click="confirmingDelete = true"
              >🗑 delete</button>
            </div>
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

        <!-- Row 1: Focus (2 cols) + Health (1 col) -->
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-4 items-stretch">
          <div class="xl:col-span-2 flex">
            <ProjectContextEditor v-if="editingContext" :project="projects.active" class="w-full" @close="editingContext = false" />
            <ProjectFocusCard v-else :project="projects.active" class="w-full" />
          </div>
          <ProjectHealthCard :slug="projects.active.slug" class="w-full" />
        </div>

        <!-- Row 2: Infra + Stack + Tags (3 cols) -->
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-4 items-stretch">
          <ProjectInfraCard :project="projects.active" class="w-full" />
          <ProjectStackEditor :project="projects.active" class="w-full" />
          <ProjectTagsEditor :project="projects.active" class="w-full" />
        </div>

        <!-- Row 3: Links + Environments (2+1 cols) -->
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-4 items-stretch">
          <div class="xl:col-span-2">
            <ProjectLinksCommands :project="projects.active" class="w-full" />
          </div>
          <ProjectEnvironmentsCard :project="projects.active" class="w-full" />
        </div>

        <!-- Row 3.5: Secrets (full-width for clarity) -->
        <ProjectSecretsCard :project="projects.active" class="mb-4" />

        <!-- Row 4+: deep-work cards (collapsible, full width) -->
        <ProjectSessionsCard :project="projects.active" class="mb-4" />
        <ProjectDecisionsCard :project="projects.active" class="mb-4" />
        <ProjectLaunchesCard :project="projects.active" class="mb-4" />
        <ProjectNotesCard :project="projects.active" class="mb-4" />

        <!-- Activity timeline at bottom -->
        <ProjectActivityTimeline :project-slug="projects.active.slug" />

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
