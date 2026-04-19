# Phase 14 — GitHub Import UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** `/import/github` page — connect GitHub (OAuth), list repos, multi-select, bulk import into projects. Cockpit polish throughout.

**Prerequisite:** Phase 13 complete (HEAD ≥ `4eb1f52`).

---

## Pages

- `/import/github` — two states:
  - **Not connected:** centered CTA "Connect GitHub"
  - **Connected:** paginated repo list with checkbox multi-select + search + "Import N repos" button

---

## Files

```
frontend/src/
├── pages/
│   └── ImportGitHub.vue
└── components/
    └── import/
        ├── GitHubRepoRow.vue            single repo row with checkbox + lang/star/pushed
        └── ImportSummary.vue            sticky footer bar: "Import 7 repos"
```

---

## Task 14.1 — GitHubRepoRow component

**File:** `frontend/src/components/import/GitHubRepoRow.vue`

```vue
<script setup lang="ts">
import SignalDot from "@/components/ui/SignalDot.vue";
import type { components } from "@/api/types.gen";

type Repo = components["schemas"]["GitHubRepoOut"];

interface Props {
  repo: Repo;
  selected: boolean;
  alreadyImported?: boolean;
}
const props = defineProps<Props>();
defineEmits<{ (e: "toggle"): void }>();

function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toISOString().slice(0, 10);
}
</script>

<template>
  <label
    :class="[
      'flex items-center gap-3 px-3 py-2.5 rounded-md cursor-pointer group',
      'transition-colors duration-fast ease-out',
      alreadyImported
        ? 'opacity-50 cursor-not-allowed'
        : (selected ? 'bg-signal-green-bg' : 'hover:bg-bg-surface/60'),
    ]"
  >
    <input
      type="checkbox"
      :checked="selected"
      :disabled="alreadyImported"
      class="shrink-0 accent-signal-green w-4 h-4 rounded-sm cursor-pointer disabled:cursor-not-allowed"
      @change="$emit('toggle')"
    />
    <div class="flex-1 min-w-0">
      <div class="flex items-baseline gap-2 flex-wrap">
        <span class="font-mono text-body text-fg-primary truncate">{{ repo.full_name }}</span>
        <span
          v-if="repo.private"
          class="font-mono text-[10px] px-1.5 py-0.5 rounded-sm"
          :style="{ background: 'var(--signal-amber-bg)', color: 'var(--signal-amber)' }"
        >private</span>
        <span
          v-if="alreadyImported"
          class="font-mono text-[10px] px-1.5 py-0.5 rounded-sm"
          :style="{ background: 'var(--signal-blue-bg)', color: 'var(--signal-blue)' }"
        >already imported</span>
      </div>
      <p
        v-if="repo.description"
        class="text-small text-fg-muted truncate mt-0.5"
      >{{ repo.description }}</p>
    </div>

    <div class="shrink-0 flex items-center gap-4 text-small mono">
      <div v-if="repo.language" class="flex items-center gap-1.5 text-fg-muted">
        <SignalDot tone="blue" :glow="false" />
        <span>{{ repo.language }}</span>
      </div>
      <div class="text-fg-subtle tabular-nums w-[5rem] text-right">
        {{ shortDate(repo.pushed_at) }}
      </div>
    </div>
  </label>
</template>
```

Commit: `feat(frontend): GitHubRepoRow component (checkbox + metadata + already-imported state)`

---

## Task 14.2 — ImportSummary (sticky footer)

**File:** `frontend/src/components/import/ImportSummary.vue`

```vue
<script setup lang="ts">
import PrimaryButton from "@/components/ui/PrimaryButton.vue";

interface Props {
  count: number;
  importing: boolean;
}
defineProps<Props>();
defineEmits<{ (e: "import"): void; (e: "clear"): void }>();
</script>

<template>
  <transition
    enter-active-class="transition-all duration-med ease-out"
    enter-from-class="opacity-0 translate-y-4"
    enter-to-class="opacity-100 translate-y-0"
    leave-active-class="transition-all duration-fast ease-in"
    leave-from-class="opacity-100 translate-y-0"
    leave-to-class="opacity-0 translate-y-4"
  >
    <div
      v-if="count > 0 || importing"
      class="fixed bottom-6 left-1/2 -translate-x-1/2 z-30 glass rounded-xl shadow-modal px-5 py-3 flex items-center gap-4"
      style="background: rgba(13, 18, 26, 0.95)"
    >
      <p class="text-body">
        <span class="tabular-nums text-fg-primary font-semibold">{{ count }}</span>
        <span class="text-fg-muted ml-2">{{ count === 1 ? "repo selected" : "repos selected" }}</span>
      </p>
      <button
        type="button"
        class="text-small text-fg-muted hover:text-fg-body transition-colors"
        :disabled="importing"
        @click="$emit('clear')"
      >clear</button>
      <PrimaryButton :disabled="count === 0" :loading="importing" @click="$emit('import')">
        <span>Import {{ count }} {{ count === 1 ? "repo" : "repos" }}</span>
      </PrimaryButton>
    </div>
  </transition>
</template>
```

Commit: `feat(frontend): ImportSummary sticky footer bar`

---

## Task 14.3 — ImportGitHub page

**File:** `frontend/src/pages/ImportGitHub.vue` (new)

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import GitHubRepoRow from "@/components/import/GitHubRepoRow.vue";
import ImportSummary from "@/components/import/ImportSummary.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";

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
        Pull your repos in as Hangar projects. Stack + language + license auto-fill.
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
          We'll read your repos so you can pick which become Hangar projects. Read-only access to metadata — no code is cloned.
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
          <span class="text-fg-body">{{ integration.config?.login ?? "—" }}</span>
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
        class="w-full h-10 px-3 mb-4 rounded-md font-sans text-body bg-bg-surface/60 border border-border text-fg-primary placeholder:text-fg-subtle"
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
          class="h-9 px-4 rounded-md text-small border border-border bg-bg-surface/50 text-fg-muted hover:bg-bg-surface-hi hover:text-fg-body transition-colors"
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
```

Wire route in `frontend/src/router/index.ts`. Add:

```ts
{
  path: "/import/github",
  name: "import-github",
  component: () => import("@/pages/ImportGitHub.vue"),
},
```

(Replace the current placeholder route if there was one; otherwise add to the routes array.)

Commit: `feat(frontend): /import/github page — connect + repo list + bulk import flow`

---

## Task 14.4 — Smoke test

**File:** `frontend/src/pages/__tests__/ImportGitHub.spec.ts`

```ts
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";

import ImportGitHub from "../ImportGitHub.vue";
import { api } from "@/api/client";
import { useProjectsStore } from "@/stores/projects";

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/import/github", name: "import-github", component: ImportGitHub },
      { path: "/p/:slug", name: "pd", component: { template: "<div/>" } },
    ],
  });
}

describe("ImportGitHub", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("shows connect CTA when not connected", async () => {
    vi.spyOn(api, "GET").mockImplementation(((path: string) => {
      if (path === "/api/v1/integrations") {
        return Promise.resolve({ data: [], error: undefined, response: {} });
      }
      return Promise.resolve({ data: [], error: undefined, response: {} });
    }) as unknown as typeof api.GET);

    const router = makeRouter();
    await router.push("/import/github");
    await router.isReady();
    const wrapper = mount(ImportGitHub, { global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.text()).toContain("Connect your GitHub");
  });

  it("shows repo list when connected", async () => {
    vi.spyOn(api, "GET").mockImplementation(((path: string) => {
      if (path === "/api/v1/integrations") {
        return Promise.resolve({
          data: [{ id: "1", kind: "github", connected_at: "2026-01-01T00:00:00Z", config: { login: "lenny" } }],
          error: undefined,
          response: {},
        });
      }
      if (path === "/api/v1/integrations/github/repos") {
        return Promise.resolve({
          data: [{
            owner: "lenny",
            name: "butlr",
            full_name: "lenny/butlr",
            description: "Openclaw",
            private: false,
            default_branch: "main",
            language: "Python",
            license_spdx: "MIT",
            homepage: null,
            clone_url: "https://github.com/lenny/butlr.git",
            pushed_at: "2026-04-18T10:00:00Z",
          }],
          error: undefined,
          response: {},
        });
      }
      if (path === "/api/v1/projects") {
        return Promise.resolve({ data: { items: [], next_cursor: null }, error: undefined, response: {} });
      }
      return Promise.resolve({ data: [], error: undefined, response: {} });
    }) as unknown as typeof api.GET);

    const router = makeRouter();
    await router.push("/import/github");
    await router.isReady();
    const wrapper = mount(ImportGitHub, { global: { plugins: [router] } });
    await flushPromises();
    await flushPromises();
    const text = wrapper.text();
    expect(text).toContain("lenny/butlr");
    expect(text).toContain("connected as");
    expect(text.toLowerCase()).toContain("lenny");
  });
});
```

Commit: `test(frontend): ImportGitHub smoke tests (connect CTA + connected repo list)`

---

## Phase 14 complete when

- [ ] `/import/github` renders connect CTA when no integration.
- [ ] After OAuth, page shows repo list with multi-select.
- [ ] Filter input narrows list client-side.
- [ ] Already-imported repos (matching derived slug) show as disabled "already imported".
- [ ] Clicking "Import N repos" POSTs and shows success/warning/error toasts.
- [ ] Sticky footer appears only when something is selected.
- [ ] `pnpm typecheck` + `pnpm test --run` + `pnpm build` green.
- [ ] 4 commits on main (14.1–14.4).
