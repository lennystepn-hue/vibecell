<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import ConnectModal from "@/components/connections/ConnectModal.vue";
import ProjectCard from "@/components/projects/ProjectCard.vue";
import QuickAddProject from "@/components/projects/QuickAddProject.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useConnectionsStore } from "@/stores/connections";
import { useProjectsStore } from "@/stores/projects";

const projects = useProjectsStore();
const connections = useConnectionsStore();
const router = useRouter();
const quickAddOpen = ref(false);
const connectOpen = ref(false);
const hasOAuthClient = computed(() => connections.list.some((c) => c.type === "oauth"));

const ONBOARDING_FLAG = "vibecell_onboarding_done";

onMounted(async () => {
  await Promise.all([projects.fetchList(), connections.refresh()]);

  // Spec-6 C3 — first-empty-dashboard redirect to the wizard. We only fire
  // once per browser (localStorage flag) so dropping back to /p after the
  // user explicitly archives every project doesn't trap them in onboarding.
  const seen = (() => {
    try {
      return localStorage.getItem(ONBOARDING_FLAG) === "1";
    } catch {
      return false;
    }
  })();
  if (!seen && projects.list.length === 0) {
    router.replace("/welcome");
  }
});
</script>

<template>
  <div class="max-w-[1400px] mx-auto px-4 sm:px-6 py-6 sm:py-8">
    <!-- Header: stacks on mobile so the 2 action buttons get their own row
         instead of squishing the title or being cut off. -->
    <header class="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-4 mb-6 sm:mb-8">
      <div>
        <h1 class="text-title sm:text-display text-fg-primary tracking-tight">Projects</h1>
        <p class="text-fg-muted mt-1">
          <span class="tabular-nums">{{ projects.list.length }}</span>
          {{ projects.list.length === 1 ? "project" : "projects" }} in your workspace
        </p>
      </div>
      <div class="flex gap-2 flex-wrap">
        <RouterLink
          to="/import/github"
          class="inline-flex h-10 items-center gap-2 rounded-md px-4 font-medium text-body border border-border bg-bg-surface text-fg-body hover:bg-bg-surface-hi transition-colors"
        >
          <span aria-hidden="true">↗</span>
          <span class="hidden sm:inline">Import from GitHub</span>
          <span class="sm:hidden">Import</span>
        </RouterLink>
        <PrimaryButton @click="quickAddOpen = true">
          <span aria-hidden="true">+</span>
          <span>New project</span>
        </PrimaryButton>
      </div>
    </header>

    <section
      v-if="!connections.loading && !hasOAuthClient"
      class="glass rounded-lg p-6 mb-8 border border-signal-green/30"
    >
      <div class="flex items-center justify-between gap-4">
        <div>
          <h2 class="text-body text-fg-primary font-medium">Connect your editor to Vibecell</h2>
          <p class="text-small text-fg-muted mt-1 max-w-lg">
            Claude Desktop, Cursor, Zed, and other MCP clients can talk to Vibecell directly.
            Zero install — sign in, allow, done.
          </p>
        </div>
        <button
          class="shrink-0 px-4 py-2 rounded-md bg-signal-green text-bg-base text-body font-medium hover:opacity-90 transition-opacity"
          @click="connectOpen = true"
        >
          Connect
        </button>
      </div>
    </section>

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
          class="inline-flex h-10 items-center gap-2 rounded-md px-4 font-medium text-body border border-border bg-bg-surface text-fg-body hover:bg-bg-surface-hi transition-colors"
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
    <ConnectModal :open="connectOpen" @close="connectOpen = false" />
  </div>
</template>
