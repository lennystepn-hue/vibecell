# Phase 12 — Command Palette (⌘K)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** A snappy global palette — ⌘K/Ctrl+K opens, `>` prompt, fuzzy-match across projects, keyboard nav with ↑↓/⏎/Esc, two sections (PROJECTS + ACTIONS). Sub-100ms switch.

**Prerequisite:** Phase 11 complete (HEAD ≥ `663a23e`). Stores, projects list, routing all in place.

---

## Files

```
frontend/src/
├── components/
│   └── palette/
│       ├── CommandPalette.vue            modal + overlay + filtering + nav
│       ├── PaletteItem.vue               single row (emoji/icon + label + hint + shortcut)
│       └── PaletteSection.vue            section header (uppercase mono)
├── composables/
│   ├── useShortcut.ts                    keydown listener for Ctrl/⌘+K etc.
│   └── useFuzzyMatch.ts                  simple fuzzy matcher + scorer
└── App.vue                               (modify) mount <CommandPalette /> globally
```

---

## Task 12.1 — `useShortcut` composable

**File:** `frontend/src/composables/useShortcut.ts`

```ts
import { onMounted, onUnmounted } from "vue";

interface Options {
  key: string;       // e.g. "k"
  meta?: boolean;    // ⌘ on mac, ctrl on pc (we check either)
  preventDefault?: boolean;
}

/**
 * Register a global keydown handler. Returns cleanup via onUnmounted.
 * Use `meta: true` to require cmd/ctrl modifier (cross-OS).
 */
export function useShortcut(options: Options, handler: (ev: KeyboardEvent) => void): void {
  function onKey(ev: KeyboardEvent) {
    if (ev.key.toLowerCase() !== options.key.toLowerCase()) return;
    if (options.meta && !(ev.metaKey || ev.ctrlKey)) return;
    if (!options.meta && (ev.metaKey || ev.ctrlKey)) return;
    if (options.preventDefault !== false) ev.preventDefault();
    handler(ev);
  }
  onMounted(() => window.addEventListener("keydown", onKey));
  onUnmounted(() => window.removeEventListener("keydown", onKey));
}
```

Commit: `feat(frontend): useShortcut composable (Ctrl/⌘-aware global keydown registration)`

---

## Task 12.2 — `useFuzzyMatch`

**File:** `frontend/src/composables/useFuzzyMatch.ts`

```ts
/**
 * Lightweight fuzzy matcher: returns a score for `query` matched against
 * `target` (higher is better), or null if no match. Prefix matches score highest,
 * contiguous substring matches second, subsequence matches third.
 */
export function fuzzyScore(query: string, target: string): number | null {
  if (!query) return 0;
  const q = query.toLowerCase();
  const t = target.toLowerCase();
  if (t === q) return 1000;
  if (t.startsWith(q)) return 900 - (t.length - q.length);
  const idx = t.indexOf(q);
  if (idx === 0) return 800;
  if (idx > 0) return 700 - idx;

  // Subsequence match: every char of q appears in t in order.
  let qi = 0;
  let lastMatchIdx = -1;
  let gap = 0;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      if (lastMatchIdx >= 0) gap += ti - lastMatchIdx - 1;
      lastMatchIdx = ti;
      qi++;
    }
  }
  if (qi < q.length) return null;
  return Math.max(0, 500 - gap * 5 - (t.length - q.length));
}

export function fuzzyFilter<T>(
  query: string,
  items: T[],
  getKey: (item: T) => string,
): T[] {
  if (!query) return items;
  return items
    .map((item) => ({ item, score: fuzzyScore(query, getKey(item)) }))
    .filter((entry): entry is { item: T; score: number } => entry.score !== null)
    .sort((a, b) => b.score - a.score)
    .map((entry) => entry.item);
}
```

Commit: `feat(frontend): useFuzzyMatch — prefix/substring/subsequence scorer`

---

## Task 12.3 — Palette item + section

**File:** `frontend/src/components/palette/PaletteSection.vue`

```vue
<script setup lang="ts">
defineProps<{ label: string }>();
</script>

<template>
  <div
    class="px-4 pt-3 pb-1 mono-label"
    style="border-top: 1px solid var(--border-subtle)"
  >
    {{ label }}
  </div>
</template>
```

**File:** `frontend/src/components/palette/PaletteItem.vue`

```vue
<script setup lang="ts">
interface Props {
  selected: boolean;
  icon?: string;
  label: string;
  hint?: string;
  shortcut?: string;
}
defineProps<Props>();

defineEmits<{ (e: "click"): void; (e: "hover"): void }>();
</script>

<template>
  <button
    type="button"
    :class="[
      'w-full flex items-center gap-3 px-4 h-10 text-left',
      'font-sans text-body',
      'transition-colors duration-fast ease-out',
      selected ? 'bg-bg-surface-hi text-fg-primary' : 'text-fg-body hover:bg-bg-surface/60',
    ]"
    @click="$emit('click')"
    @mouseenter="$emit('hover')"
  >
    <span
      v-if="icon"
      class="text-[16px] leading-none shrink-0 w-5 text-center"
      aria-hidden="true"
    >{{ icon }}</span>
    <span class="flex-1 truncate">{{ label }}</span>
    <span v-if="hint" class="mono text-small text-fg-muted">{{ hint }}</span>
    <kbd
      v-if="shortcut"
      class="font-mono text-[10px] px-1.5 py-0.5 rounded-sm"
      style="background: var(--signal-blue-bg); color: var(--fg-muted); border: 1px solid var(--border-subtle)"
    >{{ shortcut }}</kbd>
  </button>
</template>
```

Commit: `feat(frontend): PaletteItem + PaletteSection — Cockpit row primitives`

---

## Task 12.4 — CommandPalette

**File:** `frontend/src/components/palette/CommandPalette.vue`

```vue
<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useRouter } from "vue-router";

import PaletteItem from "./PaletteItem.vue";
import PaletteSection from "./PaletteSection.vue";
import { fuzzyFilter } from "@/composables/useFuzzyMatch";
import { useShortcut } from "@/composables/useShortcut";
import { useCommandPaletteStore } from "@/stores/command-palette";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type ProjectListItem = components["schemas"]["ProjectListItem"];

interface ActionItem {
  kind: "action";
  id: string;
  label: string;
  icon: string;
  shortcut?: string;
  run: () => void | Promise<void>;
}

interface ProjectItem {
  kind: "project";
  id: string;
  project: ProjectListItem;
}

type PaletteRow = ActionItem | ProjectItem;

const palette = useCommandPaletteStore();
const projects = useProjectsStore();
const router = useRouter();
const toast = useToastStore();

const inputRef = ref<HTMLInputElement | null>(null);

// ⌘/Ctrl+K toggles the palette globally.
useShortcut({ key: "k", meta: true }, () => {
  palette.toggle();
});

// On open, focus the input; on close, blur.
watch(
  () => palette.open,
  async (isOpen) => {
    if (isOpen) {
      if (projects.list.length === 0) projects.fetchList();
      await nextTick();
      inputRef.value?.focus();
    }
  },
);

const actions = computed<ActionItem[]>(() => [
  {
    kind: "action",
    id: "new-project",
    label: "New project",
    icon: "+",
    shortcut: "N",
    run: () => {
      router.push("/p/new");
      palette.hide();
    },
  },
  {
    kind: "action",
    id: "import-github",
    label: "Import from GitHub",
    icon: "↗",
    shortcut: "I",
    run: () => {
      router.push("/import/github");
      palette.hide();
    },
  },
  {
    kind: "action",
    id: "settings",
    label: "Settings",
    icon: "⚙",
    shortcut: ",",
    run: () => {
      router.push("/settings");
      palette.hide();
    },
  },
]);

const matchedProjects = computed(() =>
  fuzzyFilter(palette.query, projects.list, (p) => `${p.slug} ${p.name}`).slice(0, 8),
);

const matchedActions = computed(() =>
  fuzzyFilter(palette.query, actions.value, (a) => a.label),
);

const rows = computed<PaletteRow[]>(() => [
  ...matchedProjects.value.map<ProjectItem>((p) => ({ kind: "project", id: p.id, project: p })),
  ...matchedActions.value.map<ActionItem>((a) => a),
]);

// Reset selection when rows change.
watch(rows, () => {
  palette.selectedIndex = 0;
});

function runRow(row: PaletteRow) {
  if (row.kind === "project") {
    palette.hide();
    void (async () => {
      const ok = await projects.switchTo(row.project.slug);
      if (ok) {
        router.push(`/p/${row.project.slug}`);
      } else {
        toast.push(`Couldn't switch to ${row.project.slug}`, "error");
      }
    })();
  } else {
    row.run();
  }
}

function onKeydown(ev: KeyboardEvent) {
  if (ev.key === "Escape") {
    ev.preventDefault();
    palette.hide();
    return;
  }
  if (ev.key === "ArrowDown") {
    ev.preventDefault();
    palette.selectedIndex = Math.min(rows.value.length - 1, palette.selectedIndex + 1);
    return;
  }
  if (ev.key === "ArrowUp") {
    ev.preventDefault();
    palette.selectedIndex = Math.max(0, palette.selectedIndex - 1);
    return;
  }
  if (ev.key === "Enter") {
    ev.preventDefault();
    const row = rows.value[palette.selectedIndex];
    if (row) runRow(row);
  }
}

function onBackdropClick(ev: MouseEvent) {
  if (ev.target === ev.currentTarget) {
    palette.hide();
  }
}

// Derive per-row indices so PROJECTS and ACTIONS sections can both show correct selection.
function rowIndex(kind: "project" | "action", id: string): number {
  return rows.value.findIndex((r) => r.kind === kind && r.id === id);
}
</script>

<template>
  <transition
    enter-active-class="transition-opacity duration-fast ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-fast ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="palette.open"
      class="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
      style="background: var(--bg-overlay)"
      @click="onBackdropClick"
    >
      <div
        class="w-full max-w-[640px] glass rounded-xl overflow-hidden shadow-modal"
        style="background: rgba(13, 18, 26, 0.85); border-color: var(--border-default)"
        @click.stop
      >
        <div class="flex items-center gap-3 px-4 h-12 border-b border-border-subtle">
          <span class="font-mono text-signal-green select-none" aria-hidden="true">&gt;</span>
          <input
            ref="inputRef"
            v-model="palette.query"
            type="text"
            placeholder="switch project, run action…"
            class="flex-1 bg-transparent outline-none text-body text-fg-primary placeholder:text-fg-subtle"
            spellcheck="false"
            autocorrect="off"
            autocapitalize="off"
            @keydown="onKeydown"
          />
          <kbd
            class="font-mono text-[10px] px-1.5 py-0.5 rounded-sm"
            style="background: var(--signal-blue-bg); color: var(--fg-muted); border: 1px solid var(--border-subtle)"
          >Esc</kbd>
        </div>

        <div class="max-h-[60vh] overflow-y-auto pb-2">
          <template v-if="rows.length === 0">
            <p class="px-4 py-8 text-center text-fg-muted text-small">
              No matches for "<span class="font-mono">{{ palette.query }}</span>".
            </p>
          </template>
          <template v-else>
            <template v-if="matchedProjects.length > 0">
              <PaletteSection label="projects" />
              <PaletteItem
                v-for="p in matchedProjects"
                :key="p.id"
                :selected="palette.selectedIndex === rowIndex('project', p.id)"
                :icon="p.emoji || '📦'"
                :label="p.name"
                :hint="p.slug"
                @click="runRow({ kind: 'project', id: p.id, project: p })"
                @hover="palette.selectedIndex = rowIndex('project', p.id)"
              />
            </template>

            <template v-if="matchedActions.length > 0">
              <PaletteSection label="actions" />
              <PaletteItem
                v-for="a in matchedActions"
                :key="a.id"
                :selected="palette.selectedIndex === rowIndex('action', a.id)"
                :icon="a.icon"
                :label="a.label"
                :shortcut="a.shortcut"
                @click="runRow(a)"
                @hover="palette.selectedIndex = rowIndex('action', a.id)"
              />
            </template>
          </template>
        </div>
      </div>
    </div>
  </transition>
</template>
```

Wire into `App.vue` (modify):

```vue
<script setup lang="ts">
import AppLayout from "@/components/app/AppLayout.vue";
import CommandPalette from "@/components/palette/CommandPalette.vue";
</script>

<template>
  <AppLayout>
    <RouterView />
  </AppLayout>
  <CommandPalette />
</template>
```

Commit: `feat(frontend): CommandPalette — global ⌘K switcher with fuzzy search + keyboard nav`

---

## Task 12.5 — Tests

**File:** `frontend/src/components/palette/__tests__/CommandPalette.spec.ts`

```ts
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";

import CommandPalette from "../CommandPalette.vue";
import { useCommandPaletteStore } from "@/stores/command-palette";
import { useProjectsStore } from "@/stores/projects";

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/p/:slug", name: "project-detail", component: { template: "<div/>" } },
      { path: "/p/new", name: "p-new", component: { template: "<div/>" } },
      { path: "/import/github", name: "import", component: { template: "<div/>" } },
      { path: "/settings", name: "settings", component: { template: "<div/>" } },
    ],
  });
}

function seed(ps = useProjectsStore()) {
  ps.list = [
    { id: "1", slug: "butlr", name: "Butlr", emoji: "🛎️", color: null, pitch: null, status: "building" },
    { id: "2", slug: "zapline", name: "Zapline", emoji: "⚡", color: null, pitch: null, status: "live" },
  ];
  vi.spyOn(ps, "fetchList").mockResolvedValue();
  vi.spyOn(ps, "switchTo").mockResolvedValue(true);
}

describe("CommandPalette", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("is hidden by default, visible when store.open=true", async () => {
    const wrapper = mount(CommandPalette, { global: { plugins: [makeRouter()] } });
    const cp = useCommandPaletteStore();
    expect(wrapper.find("input").exists()).toBe(false);
    cp.show();
    await flushPromises();
    expect(wrapper.find("input").exists()).toBe(true);
  });

  it("lists projects and actions when open", async () => {
    const ps = useProjectsStore();
    seed(ps);
    const wrapper = mount(CommandPalette, { global: { plugins: [makeRouter()] } });
    const cp = useCommandPaletteStore();
    cp.show();
    await flushPromises();
    const text = wrapper.text();
    expect(text).toContain("projects");
    expect(text).toContain("butlr");
    expect(text).toContain("zapline");
    expect(text).toContain("actions");
    expect(text).toContain("New project");
  });

  it("filters via fuzzy match on query", async () => {
    const ps = useProjectsStore();
    seed(ps);
    const wrapper = mount(CommandPalette, { global: { plugins: [makeRouter()] } });
    const cp = useCommandPaletteStore();
    cp.show();
    await flushPromises();
    await wrapper.find("input").setValue("zap");
    await flushPromises();
    const text = wrapper.text();
    expect(text).toContain("zapline");
    expect(text).not.toContain("butlr");
  });

  it("closes on Escape", async () => {
    const wrapper = mount(CommandPalette, { global: { plugins: [makeRouter()] } });
    const cp = useCommandPaletteStore();
    cp.show();
    await flushPromises();
    await wrapper.find("input").trigger("keydown", { key: "Escape" });
    expect(cp.open).toBe(false);
  });
});
```

Run `pnpm test --run` — expect 7 (earlier) + 4 = 11 passed.

Commit: `test(frontend): CommandPalette smoke tests (toggle, listing, filter, escape)`

---

## Phase 12 complete when

- [ ] ⌘K/Ctrl+K opens the palette globally.
- [ ] Mono `>` prompt + glass + backdrop blur visible.
- [ ] Fuzzy filter across projects + actions works.
- [ ] ↑↓/⏎/Esc keyboard navigation works.
- [ ] Click outside closes.
- [ ] `pnpm typecheck` + `pnpm test --run` + `pnpm build` green.
- [ ] 5 commits on main (12.1–12.5).
