<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import AppLayout from "@/components/app/AppLayout.vue";
import MonoLabel from "@/components/ui/MonoLabel.vue";
import { api } from "@/api/client";

interface SearchHit {
  entity: string;
  entity_id: string;
  project_slug: string | null;
  project_id: string | null;
  title: string | null;
  snippet: string;
  rank: number;
}

const route = useRoute();
const router = useRouter();

const query = ref("");
const queryInput = ref("");
const loading = ref(false);
const results = ref<SearchHit[]>([]);
const recentSearches = ref<string[]>([]);

const RECENT_KEY = "vibecell:recent-searches";

function loadRecent() {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    recentSearches.value = raw ? JSON.parse(raw) : [];
  } catch {
    recentSearches.value = [];
  }
}

function rememberQuery(q: string) {
  const next = [q, ...recentSearches.value.filter((x) => x !== q)].slice(0, 5);
  recentSearches.value = next;
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    // noop
  }
}

async function runSearch(q: string) {
  const trimmed = q.trim();
  if (!trimmed) {
    results.value = [];
    return;
  }
  loading.value = true;
  try {
    const { data, error } = await api.GET("/api/v1/search", {
      params: { query: { q: trimmed, limit: 50 } },
    });
    if (error) {
      results.value = [];
    } else {
      results.value = (data as unknown as SearchHit[]) ?? [];
      rememberQuery(trimmed);
    }
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadRecent();
  const q = (route.query.q as string | undefined) ?? "";
  queryInput.value = q;
  query.value = q;
  if (q) void runSearch(q);
});

watch(
  () => route.query.q,
  (next) => {
    const q = (next as string | undefined) ?? "";
    queryInput.value = q;
    query.value = q;
    if (q) void runSearch(q);
    else results.value = [];
  },
);

function onSubmit() {
  const q = queryInput.value.trim();
  if (!q) return;
  router.push({ path: "/search", query: { q } });
}

function resultLink(hit: SearchHit): string {
  if (hit.entity === "project" && hit.project_slug) return `/p/${hit.project_slug}`;
  if (hit.project_slug) return `/p/${hit.project_slug}`;
  if (hit.entity === "idea") return "/ideas";
  return "/";
}

const grouped = computed(() => {
  const order: string[] = ["project", "session", "decision", "idea", "note"];
  const byKind: Record<string, SearchHit[]> = {};
  for (const r of results.value) {
    const k = r.entity;
    if (!byKind[k]) byKind[k] = [];
    byKind[k].push(r);
  }
  return order
    .filter((k) => byKind[k] && byKind[k].length > 0)
    .map((k) => ({ entity: k, hits: byKind[k]! }));
});

const entityLabels: Record<string, string> = {
  project: "projects",
  session: "sessions",
  decision: "decisions",
  idea: "ideas",
  note: "notes",
};
</script>

<template>
  <AppLayout>
    <div class="max-w-[900px] mx-auto px-8 py-8">
      <header class="mb-6">
        <h1 class="text-display text-fg-primary tracking-tight">Search</h1>
        <p class="text-body text-fg-muted mt-1">FTS across projects, sessions, decisions, ideas, and notes.</p>
      </header>

      <form class="mb-6 flex gap-2" @submit.prevent="onSubmit">
        <input
          v-model="queryInput"
          type="search"
          class="flex-1 h-11 px-4 rounded-md font-sans text-body bg-bg-surface/60 border border-border text-fg-primary placeholder:text-fg-subtle"
          placeholder="Search anything…"
          autofocus
        />
        <button
          type="submit"
          class="h-11 px-5 rounded-md font-sans font-semibold text-body"
          :style="{ background: 'var(--signal-green)', color: 'var(--bg-body-to)' }"
        >Search</button>
      </form>

      <div v-if="!query && recentSearches.length === 0" class="glass rounded-lg p-6 text-center">
        <p class="text-fg-muted text-body mb-2">Try searching for something.</p>
        <p class="text-small text-fg-subtle">
          Examples: <code class="font-mono">butlr</code>,
          <code class="font-mono">stripe</code>,
          <code class="font-mono">webhook</code>.
        </p>
      </div>

      <div v-if="!query && recentSearches.length > 0" class="glass rounded-lg p-5">
        <MonoLabel>recent searches</MonoLabel>
        <ul class="mt-3 space-y-1">
          <li
            v-for="r in recentSearches"
            :key="r"
          >
            <RouterLink
              :to="{ path: '/search', query: { q: r } }"
              class="link font-mono text-small"
            >{{ r }}</RouterLink>
          </li>
        </ul>
      </div>

      <div v-if="loading" class="text-fg-muted text-small py-8 text-center">searching…</div>

      <div v-else-if="query && results.length === 0" class="text-fg-muted text-small py-12 text-center italic">
        No matches for "<span class="font-mono">{{ query }}</span>".
      </div>

      <div v-else-if="grouped.length > 0" class="space-y-6">
        <section
          v-for="g in grouped"
          :key="g.entity"
          class="glass rounded-lg p-5"
        >
          <MonoLabel>{{ entityLabels[g.entity] || g.entity }}
            <span class="opacity-60 ml-2">({{ g.hits.length }})</span>
          </MonoLabel>
          <ul class="mt-3 space-y-2">
            <li
              v-for="hit in g.hits"
              :key="`${hit.entity}:${hit.entity_id}`"
              class="p-3 rounded-md bg-bg-surface/40 hover:bg-bg-surface-hi transition-colors"
            >
              <RouterLink :to="resultLink(hit)" class="block">
                <div class="flex items-start gap-3">
                  <span class="font-mono text-[10px] uppercase text-fg-subtle shrink-0 w-16">{{ hit.entity }}</span>
                  <div class="flex-1 min-w-0">
                    <p v-if="hit.title" class="text-body text-fg-primary font-medium truncate">{{ hit.title }}</p>
                    <!-- eslint-disable-next-line vue/no-v-html -->
                    <p class="text-small text-fg-muted mt-0.5 snippet" v-html="hit.snippet" />
                    <p v-if="hit.project_slug" class="mono-label mt-1 opacity-60">
                      project: <span class="font-mono">{{ hit.project_slug }}</span>
                    </p>
                  </div>
                  <span class="font-mono text-[10px] text-fg-subtle shrink-0">{{ hit.rank.toFixed(3) }}</span>
                </div>
              </RouterLink>
            </li>
          </ul>
        </section>
      </div>
    </div>
  </AppLayout>
</template>

<style>
.snippet b {
  color: var(--signal-green);
  font-weight: 600;
}
</style>
