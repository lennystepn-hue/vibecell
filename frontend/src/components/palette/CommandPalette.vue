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

const searchAction = computed<ActionItem | null>(() => {
  const q = palette.query.trim();
  if (q.length < 3) return null;
  return {
    kind: "action",
    id: "search-all",
    label: `Search all for "${q}"`,
    icon: "⌕",
    run: () => {
      router.push({ path: "/search", query: { q } });
      palette.hide();
    },
  };
});

const rows = computed<PaletteRow[]>(() => {
  const list: PaletteRow[] = [
    ...matchedProjects.value.map<ProjectItem>((p) => ({ kind: "project", id: p.id, project: p })),
    ...matchedActions.value.map<ActionItem>((a) => a),
  ];
  if (searchAction.value) list.push(searchAction.value);
  return list;
});

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
        style="background: var(--bg-chrome); border-color: var(--border-default)"
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

            <template v-if="searchAction">
              <PaletteSection label="search all…" />
              <PaletteItem
                :selected="palette.selectedIndex === rowIndex('action', searchAction.id)"
                :icon="searchAction.icon"
                :label="searchAction.label"
                @click="runRow(searchAction)"
                @hover="palette.selectedIndex = rowIndex('action', searchAction.id)"
              />
            </template>
          </template>
        </div>
      </div>
    </div>
  </transition>
</template>
