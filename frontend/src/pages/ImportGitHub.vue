<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import GitHubRepoRow from "@/components/import/GitHubRepoRow.vue";
import ImportSummary from "@/components/import/ImportSummary.vue";

import { api } from "@/api/client";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Repo = components["schemas"]["GitHubRepoOut"];
type Integration = components["schemas"]["IntegrationOut"];

const projects = useProjectsStore();
const toast = useToastStore();
const router = useRouter();

const loading = ref(true);
const integration = ref<Integration | null>(null);
const repos = ref<Repo[]>([]);
const page = ref(1);
const loadingMore = ref(false);
const hasMore = ref(true);
const query = ref("");

const selected = ref(new Set<string>());
const importing = ref(false);

const existingSlugs = computed(() => new Set(projects.list.map((p) => p.slug)));

const connectedLogin = computed<string>(() => {
  const cfg = integration.value?.config as { login?: string } | undefined;
  return cfg?.login ?? "—";
});

function derivedSlug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 50);
}

function isAlreadyImported(repo: Repo): boolean {
  return existingSlugs.value.has(derivedSlug(repo.name));
}

const filteredRepos = computed(() => {
  if (!query.value.trim()) return repos.value;
  const q = query.value.toLowerCase();
  return repos.value.filter(
    (r) => r.full_name.toLowerCase().includes(q)
      || (r.description?.toLowerCase().includes(q) ?? false),
  );
});

async function loadIntegrations() {
  loading.value = true;
  const { data } = await api.GET("/api/v1/integrations");
  loading.value = false;
  integration.value = data?.find((i) => i.kind === "github") ?? null;
  if (integration.value) {
    await loadRepos();
    if (projects.list.length === 0) await projects.fetchList();
  }
}

async function loadRepos() {
  loadingMore.value = true;
  const { data } = await api.GET("/api/v1/integrations/github/repos", {
    params: { query: { page: page.value } },
  });
  loadingMore.value = false;
  if (!data || data.length === 0) {
    hasMore.value = false;
    return;
  }
  repos.value = [...repos.value, ...data];
  if (data.length < 30) hasMore.value = false;
}

async function loadMore() {
  page.value += 1;
  await loadRepos();
}

function toggle(fullName: string) {
  const next = new Set(selected.value);
  if (next.has(fullName)) next.delete(fullName);
  else next.add(fullName);
  selected.value = next;
}

function clearSelection() {
  selected.value = new Set();
}

async function doImport() {
  importing.value = true;
  const items = Array.from(selected.value).map((fullName) => {
    const [owner, name] = fullName.split("/");
    return { owner: owner ?? "", name: name ?? "" };
  });
  const { data, error } = await api.POST("/api/v1/integrations/github/import", {
    body: { repos: items },
  });
  importing.value = false;
  if (error || !data) {
    toast.push("Import failed", "error");
    return;
  }
  const imported = data.results.filter((r) => r.status === "imported").length;
  const skipped = data.results.filter((r) => r.status === "skipped-duplicate").length;
  const failed = data.results.filter((r) => r.status === "failed").length;

  if (imported > 0) {
    toast.push(`Imported ${imported} ${imported === 1 ? "project" : "projects"}`, "success");
  }
  if (skipped > 0) {
    toast.push(`${skipped} skipped (slug already exists)`, "warning");
  }
  if (failed > 0) {
    toast.push(`${failed} failed — see server log`, "error");
  }

  clearSelection();
  await projects.fetchList();
  if (imported === 1 && data.results.length === 1) {
    const slug = data.results[0]?.slug;
    if (slug) router.push(`/p/${slug}`);
  }
}

onMounted(() => loadIntegrations());
</script>

<template>
  <div class="max-w-[960px] mx-auto px-6 py-8">
    <header class="mb-8">
      <h1 class="text-display text-fg-primary tracking-tight">Import from GitHub</h1>
      <p class="text-fg-muted mt-1">
        Pull your repos in as Vibecell projects. Stack + language + license auto-fill.
      </p>
    </header>

    <div v-if="loading" class="text-fg-muted">
      <p class="mono-label">loading integration…</p>
    </div>

    <!-- Not connected -->
    <div
      v-else-if="!integration"
      class="glass rounded-xl p-10 flex flex-col items-center gap-5 text-center"
    >
      <div
        class="w-14 h-14 rounded-full flex items-center justify-center"
        style="background: var(--signal-green-bg); color: var(--signal-green)"
      >
        <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.15-1.11-1.46-1.11-1.46-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.9 1.53 2.36 1.09 2.93.83.09-.65.35-1.09.63-1.34-2.22-.25-4.56-1.11-4.56-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02A9.6 9.6 0 0 1 12 6.8c.85.004 1.7.11 2.5.33 1.9-1.29 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.3.68.92.68 1.86v2.76c0 .27.18.58.69.48A10 10 0 0 0 12 2z"/>
        </svg>
      </div>
      <div class="max-w-sm">
        <h2 class="text-title text-fg-primary">Connect your GitHub</h2>
        <p class="text-fg-muted mt-2">
          We'll read your repos so you can pick which become Vibecell projects. Read-only access to metadata — no code is cloned.
        </p>
      </div>
      <a
        href="/api/v1/integrations/github/oauth-start"
        class="inline-flex h-11 items-center gap-2 rounded-md px-5 font-semibold text-section"
        :style="{ background: 'var(--signal-green)', color: 'var(--bg-body-to)', boxShadow: '0 0 0 1px var(--signal-green), 0 0 16px rgba(92, 200, 164, 0.18)' }"
      >Connect GitHub</a>
    </div>

    <!-- Connected -->
    <div v-else>
      <div class="flex items-center gap-3 mb-4">
        <p class="mono-label">
          connected as
          <span class="text-fg-body">{{ connectedLogin }}</span>
        </p>
        <span class="text-fg-subtle">·</span>
        <p class="mono-label tabular-nums">
          {{ repos.length }} repo{{ repos.length === 1 ? "" : "s" }} loaded
        </p>
      </div>

      <input
        v-model="query"
        type="text"
        placeholder="filter by name or description…"
        class="w-full h-10 px-3 mb-4 rounded-md font-sans text-body bg-bg-surface border border-border text-fg-primary placeholder:text-fg-subtle"
      />

      <div class="glass rounded-lg overflow-hidden">
        <div v-if="filteredRepos.length === 0" class="p-8 text-center text-fg-muted">
          <p v-if="query">No repos match "<span class="font-mono">{{ query }}</span>"</p>
          <p v-else class="mono-label">no repos in your account</p>
        </div>
        <div v-else class="py-2">
          <GitHubRepoRow
            v-for="repo in filteredRepos"
            :key="repo.full_name"
            :repo="repo"
            :selected="selected.has(repo.full_name)"
            :already-imported="isAlreadyImported(repo)"
            @toggle="toggle(repo.full_name)"
          />
        </div>
      </div>

      <div class="mt-4 flex justify-center">
        <button
          v-if="hasMore"
          type="button"
          class="h-9 px-4 rounded-md text-small border border-border bg-bg-surface text-fg-muted hover:bg-bg-surface-hi hover:text-fg-body transition-colors"
          :disabled="loadingMore"
          @click="loadMore"
        >{{ loadingMore ? "loading…" : "load more" }}</button>
        <p v-else class="mono-label opacity-60">// end of list</p>
      </div>

      <ImportSummary
        :count="selected.size"
        :importing="importing"
        @import="doImport"
        @clear="clearSelection"
      />
    </div>
  </div>
</template>
