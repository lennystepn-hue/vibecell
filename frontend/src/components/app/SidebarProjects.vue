<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

import LivePulse from "@/components/app/LivePulse.vue";
import SignalDot from "@/components/ui/SignalDot.vue";
import { useGroupsStore } from "@/stores/groups";
import { usePresenceStore } from "@/stores/presence";
import { useProjectsStore } from "@/stores/projects";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectListItem"];

const route = useRoute();
const projects = useProjectsStore();
const groups = useGroupsStore();
const presence = usePresenceStore();
// Reference `presence` to ensure the store is instantiated even if sidebar
// mounts before App.vue's watcher fires. The actual reactivity flows through
// LivePulse component reads.
void presence;

onMounted(async () => {
  if (projects.list.length === 0) await projects.fetchList();
  if (groups.list.length === 0) await groups.fetchList();
});

const grouped = computed(() => {
  const map = new Map<string, Project[]>();
  map.set("__ungrouped__", []);
  for (const g of groups.list) map.set(g.id, []);
  const sorted = [...projects.list].sort(
    (a, b) => (a.position ?? 0) - (b.position ?? 0),
  );
  for (const p of sorted) {
    const key = p.group_id ?? "__ungrouped__";
    if (!map.has(key)) map.set("__ungrouped__", [...(map.get("__ungrouped__") ?? []), p]);
    else map.get(key)!.push(p);
  }
  return map;
});

// Collapse state persists across reloads
const COLLAPSE_KEY = "hangar.sidebar.collapsed";
const collapsed = ref<Set<string>>(
  new Set(JSON.parse(localStorage.getItem(COLLAPSE_KEY) ?? "[]")),
);
function toggleCollapse(groupKey: string) {
  const next = new Set(collapsed.value);
  if (next.has(groupKey)) next.delete(groupKey);
  else next.add(groupKey);
  collapsed.value = next;
  localStorage.setItem(COLLAPSE_KEY, JSON.stringify([...next]));
}

// Keep the sidebar dots in lockstep with StatusPill's color mapping.
const toneFor = (status: string) => {
  switch (status) {
    case "idea":
      return "violet" as const;
    case "building":
      return "teal" as const;
    case "live":
      return "green" as const;
    case "paused":
      return "amber" as const;
    case "shipped":
      return "blue" as const;
    case "dead":
      return "red" as const;
    case "archived":
    default:
      return "muted" as const;
  }
};

// ---------- drag & drop ----------
const draggingSlug = ref<string | null>(null);
const dropTargetGroup = ref<string | null>(null);

function onDragStart(ev: DragEvent, slug: string) {
  draggingSlug.value = slug;
  if (ev.dataTransfer) {
    ev.dataTransfer.effectAllowed = "move";
    ev.dataTransfer.setData("text/plain", slug);
  }
}
function onDragEnd() {
  draggingSlug.value = null;
  dropTargetGroup.value = null;
}
function onDragOverGroup(ev: DragEvent, groupKey: string) {
  if (!draggingSlug.value) return;
  ev.preventDefault();
  dropTargetGroup.value = groupKey;
}
async function onDropInGroup(ev: DragEvent, groupKey: string) {
  ev.preventDefault();
  const slug = draggingSlug.value;
  if (!slug) return;
  const newGroupId = groupKey === "__ungrouped__" ? null : groupKey;
  const groupProjects = grouped.value.get(groupKey) ?? [];
  const position = groupProjects.length;
  await groups.reorderProjects([{ slug, group_id: newGroupId, position }]);
  await projects.fetchList();
  draggingSlug.value = null;
  dropTargetGroup.value = null;
}

// ---------- context menu ----------
interface MenuState {
  x: number;
  y: number;
  projectSlug: string | null;
}
const menu = ref<MenuState | null>(null);
const groupModalOpen = ref(false);
const newGroupName = ref("");
const newGroupColor = ref("#8ab4ff");

const PRESET_COLORS = [
  "#5cc8a4",
  "#f5b84a",
  "#ff5b5b",
  "#8ab4ff",
  "#c084fc",
  "#f472b6",
  "#cfd4dc",
];

function onContextProject(ev: MouseEvent, slug: string) {
  ev.preventDefault();
  ev.stopPropagation();
  menu.value = { x: ev.clientX, y: ev.clientY, projectSlug: slug };
}
function onContextSidebar(ev: MouseEvent) {
  ev.preventDefault();
  menu.value = { x: ev.clientX, y: ev.clientY, projectSlug: null };
}
function closeMenu() {
  menu.value = null;
}
async function assignProject(groupId: string | null) {
  if (!menu.value?.projectSlug) return;
  await groups.reorderProjects([
    { slug: menu.value.projectSlug, group_id: groupId, position: 0 },
  ]);
  await projects.fetchList();
  closeMenu();
}
function openNewGroup() {
  newGroupName.value = "";
  newGroupColor.value = "#8ab4ff";
  groupModalOpen.value = true;
  closeMenu();
}
async function submitNewGroup() {
  const name = newGroupName.value.trim();
  if (!name) return;
  await groups.create(name, newGroupColor.value);
  groupModalOpen.value = false;
}
async function deleteGroup(id: string) {
  if (!confirm("Delete this group? Projects inside become ungrouped.")) return;
  await groups.remove(id);
  await projects.fetchList();
  closeMenu();
}

function rowClick() {
  if (menu.value) closeMenu();
}
</script>

<template>
  <aside
    class="chrome border-r w-[200px] shrink-0 flex flex-col h-full relative"
    @contextmenu="onContextSidebar"
    @click="rowClick"
  >
    <div class="mono-label px-3 pt-3 pb-2 flex items-center gap-2">
      <span class="tabular-nums">{{ projects.list.length }}</span>
      <span>projects</span>
    </div>
    <div class="flex-1 overflow-y-auto px-1 pb-4">
      <section
        v-if="(grouped.get('__ungrouped__') ?? []).length > 0"
        class="mb-3 rounded-md transition-colors"
        :class="dropTargetGroup === '__ungrouped__' ? 'ring-1 ring-signal-green' : ''"
        @dragover="onDragOverGroup($event, '__ungrouped__')"
        @drop="onDropInGroup($event, '__ungrouped__')"
      >
        <header
          class="mono-label px-3 py-1 cursor-pointer select-none hover:text-fg-body transition-colors"
          @click="toggleCollapse('__ungrouped__')"
        >
          <span class="mr-1 inline-block w-3">{{ collapsed.has('__ungrouped__') ? '▸' : '▾' }}</span>
          // no group
          <span class="ml-1 tabular-nums opacity-60">{{ (grouped.get('__ungrouped__') ?? []).length }}</span>
        </header>
        <div v-show="!collapsed.has('__ungrouped__')">
          <RouterLink
            v-for="p in (grouped.get('__ungrouped__') ?? [])"
            :key="p.id"
            :to="`/p/${p.slug}`"
            draggable="true"
            @dragstart="onDragStart($event, p.slug)"
            @dragend="onDragEnd"
            @contextmenu="onContextProject($event, p.slug)"
            :class="[
              'flex items-center gap-2 px-2 py-1.5 rounded-md mb-0.5 ml-2',
              'font-mono text-small',
              'transition-colors duration-fast ease-out',
              draggingSlug === p.slug ? 'opacity-50' : '',
              route.params.slug === p.slug
                ? 'bg-bg-surface-hi text-fg-primary'
                : 'text-fg-muted hover:bg-bg-surface hover:text-fg-body',
            ]"
          >
            <span
              class="text-[14px] leading-none shrink-0"
              :style="route.params.slug === p.slug ? 'filter: saturate(1)' : 'filter: saturate(0.85)'"
              aria-hidden="true"
            >{{ p.emoji || "📦" }}</span>
            <span class="truncate flex-1">{{ p.slug }}</span>
            <!-- Claude is live → show ONLY the pulsing green dot (carries the "working now" signal).
                 Otherwise show the static status-tone dot. Two green dots side-by-side looked
                 redundant when a "building" project had Claude active. -->
            <LivePulse :slug="p.slug" variant="dot" dense />
            <SignalDot v-if="!presence.isLive(p.slug)" :tone="toneFor(p.status)" :glow="false" />
          </RouterLink>
        </div>
      </section>

      <section
        v-for="g in groups.list"
        :key="g.id"
        class="mb-3 rounded-md transition-colors"
        :class="dropTargetGroup === g.id ? 'ring-1 ring-signal-green' : ''"
        @dragover="onDragOverGroup($event, g.id)"
        @drop="onDropInGroup($event, g.id)"
      >
        <header
          class="mono-label px-3 py-1 cursor-pointer select-none hover:text-fg-body transition-colors flex items-center gap-2"
          @click="toggleCollapse(g.id)"
        >
          <span class="inline-block w-3">{{ collapsed.has(g.id) ? '▸' : '▾' }}</span>
          <span
            v-if="g.color"
            class="inline-block w-1.5 h-3.5 rounded-sm shrink-0"
            :style="{ background: g.color }"
            aria-hidden="true"
          />
          <span class="truncate">{{ g.name }}</span>
          <span class="ml-auto tabular-nums opacity-60">{{ (grouped.get(g.id) ?? []).length }}</span>
        </header>
        <div
          v-show="!collapsed.has(g.id)"
          class="pl-1 ml-2 min-h-[6px]"
          :style="g.color ? `border-left: 2px solid ${g.color}` : ''"
        >
          <RouterLink
            v-for="p in (grouped.get(g.id) ?? [])"
            :key="p.id"
            :to="`/p/${p.slug}`"
            draggable="true"
            @dragstart="onDragStart($event, p.slug)"
            @dragend="onDragEnd"
            @contextmenu="onContextProject($event, p.slug)"
            :class="[
              'flex items-center gap-2 px-2 py-1.5 rounded-md mb-0.5 ml-1',
              'font-mono text-small',
              'transition-colors duration-fast ease-out',
              draggingSlug === p.slug ? 'opacity-50' : '',
              route.params.slug === p.slug
                ? 'bg-bg-surface-hi text-fg-primary'
                : 'text-fg-muted hover:bg-bg-surface hover:text-fg-body',
            ]"
          >
            <span
              class="text-[14px] leading-none shrink-0"
              :style="route.params.slug === p.slug ? 'filter: saturate(1)' : 'filter: saturate(0.85)'"
              aria-hidden="true"
            >{{ p.emoji || "📦" }}</span>
            <span class="truncate flex-1">{{ p.slug }}</span>
            <!-- Claude is live → show ONLY the pulsing green dot (carries the "working now" signal).
                 Otherwise show the static status-tone dot. Two green dots side-by-side looked
                 redundant when a "building" project had Claude active. -->
            <LivePulse :slug="p.slug" variant="dot" dense />
            <SignalDot v-if="!presence.isLive(p.slug)" :tone="toneFor(p.status)" :glow="false" />
          </RouterLink>
          <p
            v-if="(grouped.get(g.id) ?? []).length === 0"
            class="mono-label opacity-40 px-2 py-1 italic text-[10px]"
          >drop a project here</p>
        </div>
      </section>

      <p
        v-if="groups.list.length === 0 && projects.list.length > 0"
        class="mono-label opacity-50 px-3 pt-2 text-[10px] leading-relaxed"
      >// right-click to create groups</p>
    </div>
    <footer class="border-t border-border-subtle px-3 py-2 mono-label">
      <RouterLink to="/p" class="hover:text-fg-body transition-colors">← all projects</RouterLink>
    </footer>

    <div
      v-if="menu"
      class="fixed z-50 rounded-md shadow-modal py-1 min-w-[200px] border"
      :style="{
        top: menu.y + 'px',
        left: menu.x + 'px',
        background: 'var(--bg-chrome)',
        backdropFilter: 'blur(10px)',
        borderColor: 'var(--border-default)',
      }"
      @click.stop
      @contextmenu.prevent
    >
      <template v-if="menu.projectSlug">
        <div class="mono-label px-3 py-1 opacity-60">// move to group</div>
        <button
          type="button"
          class="w-full text-left px-3 py-1.5 text-small hover:bg-bg-surface-hi transition-colors"
          @click="assignProject(null)"
        >
          <span class="text-fg-muted">—</span> no group
        </button>
        <button
          v-for="g in groups.list"
          :key="g.id"
          type="button"
          class="w-full text-left px-3 py-1.5 text-small hover:bg-bg-surface-hi transition-colors flex items-center gap-2"
          @click="assignProject(g.id)"
        >
          <span
            v-if="g.color"
            class="inline-block w-2 h-2 rounded-sm"
            :style="{ background: g.color }"
          />
          <span v-else class="inline-block w-2 h-2"></span>
          {{ g.name }}
        </button>
        <div class="border-t border-border-subtle my-1"></div>
        <button
          type="button"
          class="w-full text-left px-3 py-1.5 text-small hover:bg-bg-surface-hi transition-colors text-signal-blue"
          @click="openNewGroup"
        >+ new group…</button>
      </template>
      <template v-else>
        <button
          type="button"
          class="w-full text-left px-3 py-1.5 text-small hover:bg-bg-surface-hi transition-colors text-signal-blue"
          @click="openNewGroup"
        >+ new group…</button>
        <template v-if="groups.list.length > 0">
          <div class="border-t border-border-subtle my-1"></div>
          <div class="mono-label px-3 py-1 opacity-60">// delete group</div>
          <button
            v-for="g in groups.list"
            :key="g.id"
            type="button"
            class="w-full text-left px-3 py-1.5 text-small hover:bg-signal-red-bg transition-colors flex items-center gap-2"
            @click="deleteGroup(g.id)"
          >
            <span
              v-if="g.color"
              class="inline-block w-2 h-2 rounded-sm"
              :style="{ background: g.color }"
            />
            <span v-else class="inline-block w-2 h-2"></span>
            🗑 {{ g.name }}
          </button>
        </template>
      </template>
    </div>

    <Teleport to="body">
      <div
        v-if="groupModalOpen"
        class="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
        style="background: var(--bg-overlay)"
        @click.self="groupModalOpen = false"
      >
        <div
          class="glass rounded-xl w-[400px] p-6 shadow-modal"
          style="background: var(--bg-chrome)"
        >
          <h2 class="text-section text-fg-primary font-semibold mb-4">New group</h2>
          <div class="space-y-4">
            <div>
              <label class="mono-label block mb-1.5">// name</label>
              <input
                v-model="newGroupName"
                type="text"
                placeholder="Client work"
                autofocus
                class="w-full h-10 px-3 rounded-md font-sans text-body bg-bg-surface border border-border text-fg-primary placeholder:text-fg-subtle"
                @keydown.enter="submitNewGroup"
              />
            </div>
            <div>
              <label class="mono-label block mb-1.5">// color</label>
              <div class="flex gap-2">
                <button
                  v-for="c in PRESET_COLORS"
                  :key="c"
                  type="button"
                  class="w-7 h-7 rounded-md transition-all"
                  :style="{
                    background: c,
                    'box-shadow': newGroupColor === c ? `0 0 0 2px var(--bg-body-to), 0 0 0 4px ${c}` : 'none',
                  }"
                  @click="newGroupColor = c"
                />
              </div>
            </div>
            <div class="flex justify-end gap-2 pt-2">
              <button
                type="button"
                class="h-10 px-4 text-body text-fg-muted hover:text-fg-body transition-colors"
                @click="groupModalOpen = false"
              >Cancel</button>
              <button
                type="button"
                class="h-10 px-4 rounded-md font-semibold text-body"
                :style="{ background: 'var(--signal-green)', color: 'var(--bg-body-to)' }"
                @click="submitNewGroup"
              >Create</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Spec 5B: Portfolio link -->
    <div class="border-t border-border-subtle px-1 py-2 shrink-0">
      <RouterLink
        to="/portfolio"
        class="flex items-center gap-2 px-2 py-1.5 rounded-md text-small text-fg-muted hover:text-fg-body hover:bg-bg-elevated transition-colors"
        active-class="text-fg-primary bg-bg-elevated"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        </svg>
        <span class="font-mono text-[11px] tracking-wide uppercase">Portfolio</span>
      </RouterLink>
    </div>
  </aside>
</template>
