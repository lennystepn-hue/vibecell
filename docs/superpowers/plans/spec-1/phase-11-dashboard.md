# Phase 11 — Dashboard (Cockpit showpiece)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** The central surface of Hangar — `/p` all-projects index and `/p/:slug` three-pane project detail — fully realised in Cockpit visual language.

**Prerequisite:** Phase 10 complete (HEAD ≥ `72cf9c5`). Auth pages live, Pinia stores wired, API types generated.

**Craft anchor:** every visible element maps to an explicit spec §7 decision. If a detail isn't in the spec, default to the mockup we approved during brainstorming (dark glass + phosphor-green signal + mono labels + tabular nums + sharp pills + round cards).

---

## Layout reference

```
┌─────────────────────────────────────────────────────────────┐  topbar 44px (from Phase 9)
│ ◈ lenny / butlr         switch…  ⌘K         (user menu)   │
├────────────┬────────────────────────────────┬──────────────┤
│ sidebar    │  main                          │  telemetry   │
│ 200px      │  1fr                           │  240px       │
│            │                                │              │
│ proj list  │  [ hero ]                      │  // repo     │
│  + status  │  [ focus     ][ stack    ]     │  // infra    │
│    dots    │  [ infra (preview)         ]   │  // metadata │
│  + days    │  [ context editor           ]  │  // outbound │
│    since   │  [ links | commands tabs    ]  │              │
│            │                                │              │
└────────────┴────────────────────────────────┴──────────────┘
```

---

## Files

```
frontend/src/
├── pages/
│   ├── ProjectsIndex.vue               /p — all-projects home
│   └── ProjectDetail.vue               /p/:slug — three-pane detail
├── components/
│   ├── app/
│   │   ├── SidebarProjects.vue         left pane: scrollable project list
│   │   └── ProjectTelemetryRail.vue    right pane: data rows
│   └── projects/
│       ├── ProjectCard.vue              grid card for /p index
│       ├── ProjectHero.vue              name + emoji + pitch + status pill
│       ├── ProjectFocusCard.vue         current_focus / next_step / user_wants / blocked_by
│       ├── ProjectStackCard.vue         chip list of stack items
│       ├── ProjectInfraCard.vue         read-only summary + link to tab
│       └── ProjectLinksCommands.vue     tab switcher (links | commands)
└── composables/
    └── useDaysAgo.ts                    "2d" / "3w" / "4mo" formatter
```

---

## Task 11.1 — `useDaysAgo` composable

**File:** `frontend/src/composables/useDaysAgo.ts`

```ts
export function daysAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  const days = Math.max(0, Math.floor(ms / 86_400_000));
  if (days < 1) return "today";
  if (days === 1) return "1d";
  if (days < 7) return `${days}d`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo`;
  const years = Math.floor(days / 365);
  return `${years}y`;
}
```

Commit: `feat(frontend): daysAgo formatter composable (today/1d/3w/4mo/2y)`

---

## Task 11.2 — Projects index (`/p`)

**File:** `frontend/src/components/projects/ProjectCard.vue`

```vue
<script setup lang="ts">
import { RouterLink } from "vue-router";

import StatusPill from "@/components/ui/StatusPill.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectListItem"];

defineProps<{ project: Project }>();
</script>

<template>
  <RouterLink
    :to="`/p/${project.slug}`"
    class="group block glass rounded-lg p-4 transition-all duration-fast ease-out hover:bg-bg-surface-hi hover:border-border-strong"
  >
    <div class="flex items-start gap-3 mb-2">
      <span
        class="text-[28px] leading-none transition-[filter] duration-fast"
        style="filter: saturate(0.85)"
        aria-hidden="true"
      >{{ project.emoji || "📦" }}</span>
      <div class="flex-1 min-w-0">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-section font-semibold text-fg-primary tracking-tight truncate">
            {{ project.name }}
          </h3>
          <StatusPill :status="project.status as never" />
        </div>
        <p class="mono text-small text-fg-subtle truncate mt-0.5">{{ project.slug }}</p>
      </div>
    </div>
    <p v-if="project.pitch" class="text-small text-fg-muted line-clamp-2 mt-3">
      {{ project.pitch }}
    </p>
    <p v-else class="mono-label mt-3 opacity-50">// no pitch yet</p>
  </RouterLink>
</template>

<style scoped>
.group:hover span[aria-hidden="true"] {
  filter: saturate(1) !important;
}
</style>
```

**File:** `frontend/src/pages/ProjectsIndex.vue` (full replacement)

```vue
<script setup lang="ts">
import { onMounted } from "vue";

import ProjectCard from "@/components/projects/ProjectCard.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useProjectsStore } from "@/stores/projects";

const projects = useProjectsStore();

onMounted(() => {
  projects.fetchList();
});
</script>

<template>
  <div class="max-w-[1200px] mx-auto px-6 py-8">
    <header class="flex items-baseline justify-between mb-8">
      <div>
        <h1 class="text-display text-fg-primary tracking-tight">Projects</h1>
        <p class="text-fg-muted mt-1">
          <span class="tabular-nums">{{ projects.list.length }}</span>
          in your hangar
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
        <PrimaryButton>
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
      title="Your hangar is empty."
      subtitle="Pull in your repos from GitHub or add the first one manually — either works."
    >
      <template #actions>
        <RouterLink
          to="/import/github"
          class="inline-flex h-10 items-center gap-2 rounded-md px-4 font-medium text-body border border-border bg-bg-surface/50 text-fg-body hover:bg-bg-surface-hi transition-colors"
        >
          Import from GitHub
        </RouterLink>
        <PrimaryButton>+ New project</PrimaryButton>
      </template>
    </EmptyState>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <ProjectCard
        v-for="p in projects.list"
        :key="p.id"
        :project="p"
      />
    </div>
  </div>
</template>
```

Commit: `feat(frontend): /p projects index with empty state + Cockpit project cards`

---

## Task 11.3 — Sidebar projects list (for detail page)

**File:** `frontend/src/components/app/SidebarProjects.vue`

```vue
<script setup lang="ts">
import { onMounted } from "vue";
import { RouterLink, useRoute } from "vue-router";

import SignalDot from "@/components/ui/SignalDot.vue";
import { daysAgo } from "@/composables/useDaysAgo";
import { useProjectsStore } from "@/stores/projects";

const route = useRoute();
const projects = useProjectsStore();

onMounted(() => {
  if (projects.list.length === 0) {
    projects.fetchList();
  }
});

const toneFor = (status: string) => {
  switch (status) {
    case "building":
    case "live":
      return "green";
    case "paused":
      return "amber";
    case "shipped":
      return "blue";
    case "dead":
      return "red";
    default:
      return "muted";
  }
};
</script>

<template>
  <aside class="chrome border-r w-[200px] shrink-0 flex flex-col h-full">
    <div class="mono-label px-3 pt-3 pb-2 flex items-center gap-2">
      <span class="tabular-nums">{{ projects.list.length }}</span>
      <span>projects</span>
    </div>
    <div class="flex-1 overflow-y-auto px-1">
      <RouterLink
        v-for="p in projects.list"
        :key="p.id"
        :to="`/p/${p.slug}`"
        :class="[
          'group flex items-center gap-2 px-2 py-1.5 rounded-md mb-0.5',
          'font-mono text-small',
          'transition-colors duration-fast ease-out',
          route.params.slug === p.slug
            ? 'bg-bg-surface-hi text-fg-primary'
            : 'text-fg-muted hover:bg-bg-surface/60 hover:text-fg-body',
        ]"
      >
        <span
          class="text-[14px] leading-none shrink-0 transition-[filter] duration-fast"
          :style="route.params.slug === p.slug ? 'filter: saturate(1)' : 'filter: saturate(0.85)'"
          aria-hidden="true"
        >{{ p.emoji || "📦" }}</span>
        <span class="truncate flex-1">{{ p.slug }}</span>
        <SignalDot :tone="toneFor(p.status)" :glow="false" />
      </RouterLink>
    </div>
    <footer class="border-t border-border-subtle px-3 py-2 mono-label">
      <RouterLink to="/p" class="hover:text-fg-body transition-colors">← all projects</RouterLink>
    </footer>
  </aside>
</template>
```

Commit: `feat(frontend): SidebarProjects — 200px glass pane with status dots + emoji saturation`

---

## Task 11.4 — Project detail cards (hero + focus + stack + infra + links/commands)

**File:** `frontend/src/components/projects/ProjectHero.vue`

```vue
<script setup lang="ts">
import StatusPill from "@/components/ui/StatusPill.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
defineProps<{ project: Project }>();
</script>

<template>
  <div class="flex items-start gap-4 mb-6">
    <span class="text-[44px] leading-none" aria-hidden="true">{{ project.emoji || "📦" }}</span>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-3 flex-wrap">
        <h1 class="text-display text-fg-primary tracking-tight">{{ project.name }}</h1>
        <StatusPill :status="project.status as never" />
      </div>
      <p v-if="project.pitch" class="text-body text-fg-muted mt-2 max-w-3xl">{{ project.pitch }}</p>
      <p v-else class="mono-label mt-2 opacity-50">// no pitch set</p>
    </div>
  </div>
</template>
```

**File:** `frontend/src/components/projects/ProjectFocusCard.vue`

```vue
<script setup lang="ts">
import MonoLabel from "@/components/ui/MonoLabel.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
defineProps<{ project: Project }>();
</script>

<template>
  <section class="glass rounded-lg p-5">
    <div
      v-if="project.context?.blocked_by"
      class="mb-4 px-3 py-2 rounded-sm text-small"
      :style="{ background: 'var(--signal-red-bg)', color: 'var(--signal-red)' }"
    >
      <span class="font-mono uppercase text-[10px] tracking-widest mr-2">blocked</span>
      <span>{{ project.context.blocked_by }}</span>
    </div>

    <div class="space-y-5">
      <div>
        <MonoLabel>current focus</MonoLabel>
        <p v-if="project.context?.current_focus" class="text-section text-fg-primary mt-1">
          {{ project.context.current_focus }}
        </p>
        <p v-else class="text-body text-fg-muted mt-1 italic">— not set —</p>
      </div>

      <div>
        <MonoLabel>next step</MonoLabel>
        <p v-if="project.context?.next_step" class="text-body text-fg-body mt-1">
          {{ project.context.next_step }}
        </p>
        <p v-else class="text-body text-fg-muted mt-1 italic">— not set —</p>
      </div>

      <details
        v-if="project.context?.user_wants || (project.context?.open_questions && project.context.open_questions.length > 0)"
      >
        <summary class="mono-label cursor-pointer select-none hover:text-fg-body transition-colors">
          more context ▾
        </summary>
        <div class="mt-3 space-y-4 pl-0">
          <div v-if="project.context?.user_wants">
            <MonoLabel>user wants</MonoLabel>
            <p class="text-small text-fg-muted mt-1">{{ project.context.user_wants }}</p>
          </div>
          <div
            v-if="project.context?.open_questions && project.context.open_questions.length > 0"
          >
            <MonoLabel>open questions</MonoLabel>
            <ul class="mt-1 space-y-1 list-none text-small text-fg-muted">
              <li v-for="(q, i) in project.context.open_questions" :key="i">
                <span class="text-fg-subtle mr-1">?</span>{{ q }}
              </li>
            </ul>
          </div>
        </div>
      </details>
    </div>
  </section>
</template>
```

**File:** `frontend/src/components/projects/ProjectStackCard.vue`

```vue
<script setup lang="ts">
import MonoLabel from "@/components/ui/MonoLabel.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
defineProps<{ project: Project }>();
</script>

<template>
  <section class="glass rounded-lg p-5">
    <MonoLabel>stack</MonoLabel>
    <div v-if="project.stack.length > 0" class="flex flex-wrap gap-2 mt-3">
      <span
        v-for="s in project.stack"
        :key="s.stack_item_slug"
        class="inline-flex items-center gap-1.5 px-2.5 h-6 rounded-sm font-mono text-[11px]"
        :style="{
          background: 'var(--signal-blue-bg)',
          color: 'var(--fg-body)',
          border: '1px solid var(--border-subtle)',
        }"
      >
        {{ s.name }}
      </span>
    </div>
    <p v-else class="text-small text-fg-muted italic mt-2">— nothing attached yet —</p>
  </section>
</template>
```

**File:** `frontend/src/components/projects/ProjectInfraCard.vue`

```vue
<script setup lang="ts">
import DataRow from "@/components/ui/DataRow.vue";
import MonoLabel from "@/components/ui/MonoLabel.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
defineProps<{ project: Project }>();
</script>

<template>
  <section class="glass rounded-lg p-5">
    <MonoLabel>infra</MonoLabel>
    <div v-if="project.infra" class="mt-3 space-y-0.5">
      <DataRow v-if="project.infra.domain_primary" label="domain">
        <span class="font-mono">{{ project.infra.domain_primary }}</span>
      </DataRow>
      <DataRow v-if="project.infra.server_alias" label="server">
        <span class="font-mono">{{ project.infra.server_alias }}</span>
      </DataRow>
      <DataRow v-if="project.infra.dns_provider" label="dns">
        {{ project.infra.dns_provider }}
      </DataRow>
      <DataRow v-if="project.infra.db_host" label="db">
        <span class="font-mono">{{ project.infra.db_host }}</span>
      </DataRow>
      <DataRow v-if="project.infra.cdn" label="cdn">
        {{ project.infra.cdn }}
      </DataRow>
    </div>
    <p v-else class="text-small text-fg-muted italic mt-2">— no infra configured —</p>
  </section>
</template>
```

**File:** `frontend/src/components/projects/ProjectLinksCommands.vue`

```vue
<script setup lang="ts">
import { ref } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
defineProps<{ project: Project }>();

const tab = ref<"links" | "commands">("links");
</script>

<template>
  <section class="glass rounded-lg p-0 overflow-hidden">
    <div class="flex border-b border-border-subtle">
      <button
        :class="[
          'flex-1 h-10 px-5 text-left mono-label transition-colors duration-fast',
          tab === 'links' ? 'text-fg-primary bg-bg-surface/40' : 'hover:text-fg-body',
        ]"
        @click="tab = 'links'"
      >
        links <span class="ml-1 tabular-nums opacity-60">{{ project.links.length }}</span>
      </button>
      <button
        :class="[
          'flex-1 h-10 px-5 text-left mono-label transition-colors duration-fast',
          tab === 'commands' ? 'text-fg-primary bg-bg-surface/40' : 'hover:text-fg-body',
        ]"
        @click="tab = 'commands'"
      >
        commands <span class="ml-1 tabular-nums opacity-60">{{ project.commands.length }}</span>
      </button>
    </div>

    <div v-if="tab === 'links'" class="p-5">
      <ul v-if="project.links.length > 0" class="space-y-2">
        <li v-for="l in project.links" :key="l.id" class="flex items-center gap-3">
          <span class="mono-label w-14 shrink-0 text-right">{{ l.kind || "link" }}</span>
          <a
            :href="l.url"
            target="_blank"
            rel="noopener"
            class="link text-body flex-1 truncate"
          >
            {{ l.label || l.url }}
            <span class="text-fg-subtle ml-1" aria-hidden="true">↗</span>
          </a>
        </li>
      </ul>
      <p v-else class="text-small text-fg-muted italic">— no links —</p>
    </div>

    <div v-else class="p-5">
      <ul v-if="project.commands.length > 0" class="space-y-2">
        <li
          v-for="c in project.commands"
          :key="c.id"
          class="flex flex-col gap-1 p-3 rounded-md border border-border-subtle"
        >
          <div class="flex items-center gap-2">
            <MonoLabel>{{ c.run_in }}</MonoLabel>
            <span class="text-section font-semibold text-fg-primary">{{ c.label }}</span>
          </div>
          <code class="font-mono text-small text-fg-muted truncate">{{ c.command }}</code>
        </li>
      </ul>
      <p v-else class="text-small text-fg-muted italic">— no commands saved —</p>
      <p class="mono-label opacity-50 mt-3">
        execution lands in the CLI phase (spec 3)
      </p>
    </div>
  </section>
</template>
```

Commit: `feat(frontend): project detail cards — hero/focus/stack/infra/links-commands`

---

## Task 11.5 — Telemetry rail (right pane)

**File:** `frontend/src/components/app/ProjectTelemetryRail.vue`

```vue
<script setup lang="ts">
import DataRow from "@/components/ui/DataRow.vue";
import MonoLabel from "@/components/ui/MonoLabel.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
defineProps<{ project: Project }>();

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toISOString().slice(0, 10);
}
</script>

<template>
  <aside class="chrome border-l w-[240px] shrink-0 flex flex-col h-full overflow-y-auto">
    <div class="p-4 space-y-5">
      <section>
        <MonoLabel>repo</MonoLabel>
        <div class="mt-2 space-y-0.5">
          <template v-if="project.repos.length > 0">
            <DataRow label="branch">
              <span class="font-mono">{{ project.repos[0]?.default_branch ?? "—" }}</span>
            </DataRow>
            <DataRow v-if="project.repos[0]?.primary_lang" label="lang">
              {{ project.repos[0]!.primary_lang }}
            </DataRow>
            <DataRow v-if="project.repos[0]?.license" label="license">
              <span class="font-mono">{{ project.repos[0]!.license }}</span>
            </DataRow>
          </template>
          <p v-else class="text-small text-fg-muted italic">— no repo linked —</p>
        </div>
      </section>

      <section>
        <MonoLabel>environments</MonoLabel>
        <div class="mt-2 space-y-0.5">
          <template v-if="project.environments.length > 0">
            <DataRow
              v-for="e in project.environments"
              :key="e.id"
              :label="e.kind"
            >
              <a
                v-if="e.url"
                :href="e.url"
                target="_blank"
                rel="noopener"
                class="link"
              >{{ new URL(e.url).host }}</a>
              <span v-else class="text-fg-subtle">—</span>
            </DataRow>
          </template>
          <p v-else class="text-small text-fg-muted italic">— none —</p>
        </div>
      </section>

      <section>
        <MonoLabel>metadata</MonoLabel>
        <div class="mt-2 space-y-0.5">
          <DataRow label="created">
            <span class="font-mono">{{ formatDate(project.id ? null : null) }}</span>
          </DataRow>
          <DataRow label="archived">
            <span v-if="project.archived_at" class="font-mono">{{ formatDate(project.archived_at) }}</span>
            <span v-else class="text-fg-subtle">—</span>
          </DataRow>
        </div>
      </section>

      <section>
        <MonoLabel>health</MonoLabel>
        <div class="mt-2 space-y-0.5 opacity-60">
          <DataRow label="uptime"><span class="text-fg-subtle">—</span></DataRow>
          <DataRow label="ssl"><span class="text-fg-subtle">—</span></DataRow>
          <DataRow label="issues"><span class="text-fg-subtle">—</span></DataRow>
        </div>
        <p class="mono-label opacity-50 mt-2 text-[9px] leading-relaxed">
          // monitoring activates<br>// in a later release
        </p>
      </section>
    </div>
  </aside>
</template>
```

Commit: `feat(frontend): ProjectTelemetryRail — 240px right pane with repo/env/metadata/health`

---

## Task 11.6 — Project detail page (`/p/:slug`)

**File:** `frontend/src/pages/ProjectDetail.vue` (full replacement)

```vue
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
```

Commit: `feat(frontend): /p/:slug three-pane detail page with cockpit layout`

---

## Task 11.7 — Smoke tests

**File:** `frontend/src/pages/__tests__/ProjectDetail.spec.ts`

```ts
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";

import ProjectDetail from "../ProjectDetail.vue";
import { useProjectsStore } from "@/stores/projects";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];

function fakeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "01FAKE",
    slug: "butlr",
    name: "Butlr",
    emoji: "🛎️",
    color: null,
    pitch: "OpenClaw-as-a-Service",
    status: "building",
    is_public: 0,
    archived_at: null,
    context: {
      current_focus: "Stripe webhook",
      next_step: "Handle subscription.deleted",
      user_wants: null,
      open_questions: [],
      known_issues: [],
      blocked_by: null,
    },
    infra: null,
    repos: [],
    environments: [],
    links: [],
    commands: [],
    stack: [],
    tags: [],
    ...overrides,
  };
}

describe("ProjectDetail", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  async function mountAt(slug: string, preload?: Project) {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/p", name: "projects-index", component: { template: "<div/>" } },
        { path: "/p/:slug", name: "project-detail", component: ProjectDetail },
      ],
    });
    const store = useProjectsStore();
    if (preload) {
      store.active = preload;
    }
    await router.push(`/p/${slug}`);
    await router.isReady();
    const wrapper = mount(ProjectDetail, { global: { plugins: [router] } });
    await flushPromises();
    return { wrapper, store, router };
  }

  it("renders name, pitch, and status pill from active project", async () => {
    const { wrapper } = await mountAt("butlr", fakeProject());
    expect(wrapper.text()).toContain("Butlr");
    expect(wrapper.text()).toContain("OpenClaw-as-a-Service");
    expect(wrapper.text()).toContain("building");
  });

  it("renders current focus and next step", async () => {
    const { wrapper } = await mountAt("butlr", fakeProject());
    expect(wrapper.text()).toContain("current focus");
    expect(wrapper.text()).toContain("Stripe webhook");
    expect(wrapper.text()).toContain("Handle subscription.deleted");
  });

  it("shows blocked banner when blocked_by is set", async () => {
    const { wrapper } = await mountAt(
      "butlr",
      fakeProject({
        context: {
          current_focus: "f",
          next_step: null,
          user_wants: null,
          open_questions: [],
          known_issues: [],
          blocked_by: "Waiting on Stripe API access",
        },
      }),
    );
    expect(wrapper.text().toLowerCase()).toContain("blocked");
    expect(wrapper.text()).toContain("Waiting on Stripe API access");
  });

  it("shows 'Project not found' when store.active stays null", async () => {
    const { wrapper, store } = await mountAt("nonexistent");
    store.active = null;
    await flushPromises();
    expect(wrapper.text()).toContain("Project not found");
  });
});
```

Run:
```bash
cd frontend && pnpm test --run
```

Expected: 3 (Login) + 4 (ProjectDetail) = 7 passed.

Commit: `test(frontend): ProjectDetail smoke tests (render, focus, blocked banner, 404 branch)`

---

## Phase 11 complete when

- [ ] `/p` shows empty state before projects load, then renders ProjectCards.
- [ ] `/p/:slug` renders the full three-pane layout with all cards.
- [ ] Blocked-by banner shows in red when set.
- [ ] Sidebar highlights the active slug with full-saturation emoji.
- [ ] `pnpm typecheck` + `pnpm test --run` + `pnpm build` all green.
- [ ] 7 commits on main (11.1–11.7).
