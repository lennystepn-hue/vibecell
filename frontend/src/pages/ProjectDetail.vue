<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import LivePulse from "@/components/app/LivePulse.vue";
import ProjectTelemetryRail from "@/components/app/ProjectTelemetryRail.vue";
import ProjectPreviewImage from "@/components/projects/ProjectPreviewImage.vue";
import SidebarProjects from "@/components/app/SidebarProjects.vue";
import ProjectContextEditor from "@/components/projects/ProjectContextEditor.vue";
import ShipButton from "@/components/projects/ShipButton.vue";
import ProjectOverviewChips from "@/components/projects/ProjectOverviewChips.vue";
import ProjectGridDashboard from "@/components/projects/ProjectGridDashboard.vue";
import ProjectStatusDropdown from "@/components/projects/ProjectStatusDropdown.vue";
import Confetti from "@/components/projects/Confetti.vue";
import CopyableValue from "@/components/ui/CopyableValue.vue";
import ProjectOrb from "@/components/ui/ProjectOrb.vue";
import { api } from "@/api/client";
import { useProjectLive } from "@/composables/useProjectLive";
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

// Bump to fire confetti from <Confetti :fire="…" /> — any ship.created or
// all-todos-in-batch-done event will nudge this counter.
const celebrationTick = ref(0);

// URL the mini-preview thumbnail links to. Priority mirrors the backend:
//   1. ProjectLink kind=landing
//   2. ProjectEnvironment kind=prod
//   3. Healthcheck origin
const livePreviewUrl = computed<string | null>(() => {
  const p: any = projects.active;
  if (!p) return null;
  const landing = (p.links ?? []).find((l: any) => l.kind === "landing");
  if (landing?.url) return landing.url;
  const prod = (p.environments ?? []).find((e: any) => e.kind === "prod");
  if (prod?.url) return prod.url;
  const health = (p.links ?? []).find((l: any) => l.kind === "healthcheck");
  if (health?.url) {
    try {
      const u = new URL(health.url);
      return `${u.protocol}//${u.host}`;
    } catch { /* noop */ }
  }
  return null;
});

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

// Open one SSE stream per project page. Card components subscribe via
// onProjectLiveEvent (see frontend/src/composables/useProjectLive.ts). When
// anything on the server changes for this project, the affected card self-
// refreshes without a page reload. We also trigger a confetti burst when a
// ship event fires — pure dopamine.
useProjectLive(
  () => (typeof route.params.slug === "string" ? route.params.slug : undefined),
  (ev) => {
    const slug = typeof route.params.slug === "string" ? route.params.slug : null;
    if (slug) projects.fetchProject(slug);
    if (ev.type === "ship.created") {
      celebrationTick.value += 1;
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

      <div v-else-if="projects.active" class="max-w-[1400px] px-4 sm:px-8 py-6 sm:py-8 mx-auto">

        <!-- Hero
             Mobile (< md): orb + name on row 1, status/slug/live-pulse wrap on
             row 2, ProjectPreviewImage hides (saving 80px of vertical real
             estate that the user can scroll to via the dashboard cards), and
             ShipButton + edit + delete drop to a dedicated bottom row so the
             layout never tries to fit 3 segments in <320px.
             Desktop (≥ md): unchanged side-by-side layout. -->
        <header class="mb-6">
          <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4 md:gap-6">
            <div class="flex items-start gap-3 sm:gap-4 min-w-0 flex-1">
              <ProjectOrb :seed="projects.active.slug" :size="48" class="sm:!w-14 sm:!h-14" />
              <div class="min-w-0 flex-1">
                <h1 class="text-title sm:text-display text-fg-primary tracking-tight break-words">{{ projects.active.name }}</h1>
                <div class="flex items-baseline gap-2 sm:gap-3 flex-wrap mt-2">
                  <ProjectStatusDropdown :project="projects.active" />
                  <CopyableValue :value="projects.active.slug" mono small class="text-fg-subtle" />
                  <LivePulse :slug="projects.active.slug" variant="pill" />
                </div>
                <p v-if="projects.active.pitch" class="text-body text-fg-muted mt-2 max-w-3xl">{{ projects.active.pitch }}</p>
                <!-- Created/updated timestamps only. Status is already shown by
                     the StatusPill dropdown above — no need for a redundant
                     "Active/Archived" word here. Before, that line stayed on
                     "ARCHIVED" forever because archived_at wasn't cleared when
                     status changed back. -->
                <div class="flex items-center gap-3 mt-3 text-small text-fg-subtle flex-wrap">
                  <span v-if="(projects.active as any).created_at" class="mono-label">Created {{ fmtDate((projects.active as any).created_at) }}</span>
                  <span v-if="(projects.active as any).updated_at" class="mono-label">Updated {{ fmtRel((projects.active as any).updated_at) }}</span>
                </div>
                <ProjectOverviewChips :slug="projects.active.slug" class="mt-3" />
              </div>
            </div>
            <!-- Top-right cluster.
                 Mobile: only the action row (ship + edit + delete) shown,
                 stretched full width and right-aligned. The mini preview is
                 desktop-only — it competes hard for vertical space on phones.
                 Desktop: preview thumb + actions stacked, right-aligned. -->
            <div class="flex flex-col items-stretch md:items-end gap-3 md:shrink-0">
              <ProjectPreviewImage
                :slug="projects.active.slug"
                variant="mini"
                :href="livePreviewUrl || undefined"
                empty-label="// no preview yet"
                class="hidden md:block"
              />
              <div class="flex items-center gap-3 sm:gap-2 justify-end">
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

        <!-- Inline context editor (when you hit ✎ edit in the header) -->
        <ProjectContextEditor
          v-if="editingContext"
          :project="projects.active"
          class="mb-4"
          @close="editingContext = false"
        />

        <!-- Draggable / resizable / customisable dashboard grid. -->
        <ProjectGridDashboard :project="projects.active" />

        <Confetti :fire="celebrationTick" />

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

