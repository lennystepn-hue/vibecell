<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { onProjectLiveEvent } from "@/composables/useProjectLive";

interface Todo {
  id: string;
  project_id: string;
  batch: string | null;
  title: string;
  body: string | null;
  status: "open" | "in_progress" | "done" | "cancelled";
  position: number;
  completed_by: "user" | "claude" | null;
  completion_note: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

const props = defineProps<{ project: { slug: string } }>();

const todos = ref<Todo[]>([]);
const loading = ref(false);
const newTitle = ref("");
const newBatch = ref("");
const planning = ref(false);
const planError = ref<string | null>(null);
const includeDone = ref<boolean>(
  typeof localStorage !== "undefined"
    ? localStorage.getItem(`vc:todos-include-done:${props.project.slug}`) === "true"
    : false,
);
const expanded = ref<boolean>(true);

function toggle() {
  expanded.value = !expanded.value;
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(`vc:card-expanded:todos:${props.project.slug}`, expanded.value ? "true" : "false");
  }
}

async function load() {
  const slug = props.project.slug;
  loading.value = true;
  try {
    const r = await fetch(
      `/api/v1/projects/${slug}/todos?include_done=${includeDone.value}`,
      { credentials: "include" },
    );
    if (r.ok && slug === props.project.slug) todos.value = await r.json();
  } finally {
    if (slug === props.project.slug) loading.value = false;
  }
}

async function add() {
  const title = newTitle.value.trim();
  if (!title) return;
  const body = {
    title,
    batch: newBatch.value.trim() || null,
  };
  const r = await fetch(`/api/v1/projects/${props.project.slug}/todos`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (r.ok) {
    newTitle.value = "";
    await load();
  }
}

async function aiPlan() {
  const goal = newTitle.value.trim();
  if (!goal) return;
  planning.value = true;
  planError.value = null;
  try {
    const r = await fetch(`/api/v1/projects/${props.project.slug}/ai/plan_todos`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal, commit: true }),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      planError.value = body.detail ?? `Error ${r.status}`;
      return;
    }
    newTitle.value = "";
    newBatch.value = "";
    await load();
  } catch {
    planError.value = "AI planner unreachable.";
  } finally {
    planning.value = false;
  }
}

async function toggleCompletion(t: Todo) {
  const path = t.status === "done"
    ? `/api/v1/projects/${props.project.slug}/todos/${t.id}`  // PATCH back to open
    : `/api/v1/projects/${props.project.slug}/todos/${t.id}/complete`;
  const method = t.status === "done" ? "PATCH" : "POST";
  const body = t.status === "done"
    ? JSON.stringify({ status: "open" })
    : JSON.stringify({ completed_by: "user" });
  await fetch(path, {
    method,
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body,
  });
  await load();
}

async function remove(t: Todo) {
  if (!confirm(`Delete "${t.title}"?`)) return;
  await fetch(`/api/v1/projects/${props.project.slug}/todos/${t.id}`, {
    method: "DELETE",
    credentials: "include",
  });
  await load();
}

async function setIncludeDone(v: boolean) {
  includeDone.value = v;
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(`vc:todos-include-done:${props.project.slug}`, v ? "true" : "false");
  }
  await load();
}

// Group by batch: open batches ordered by first-seen, "(no batch)" last.
const grouped = computed(() => {
  const map = new Map<string, Todo[]>();
  const ordered: string[] = [];
  for (const t of todos.value) {
    const key = t.batch ?? "__ungrouped__";
    if (!map.has(key)) {
      map.set(key, []);
      ordered.push(key);
    }
    map.get(key)!.push(t);
  }
  // Move ungrouped to the end for visual stability.
  if (ordered.includes("__ungrouped__")) {
    ordered.splice(ordered.indexOf("__ungrouped__"), 1);
    ordered.push("__ungrouped__");
  }
  return ordered.map((k) => ({
    label: k === "__ungrouped__" ? null : k,
    items: map.get(k)!,
  }));
});

function progressFor(items: Todo[]): { done: number; total: number; pct: number } {
  const total = items.length;
  const done = items.filter((t) => t.status === "done").length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  return { done, total, pct };
}

// Count of done todos — only populated when the "show done" toggle is ON
// (the server filters done rows out otherwise). For the header counter we
// fetch separately.
const doneCount = ref(0);

async function refreshDoneCount() {
  const slug = props.project.slug;
  try {
    const r = await fetch(`/api/v1/projects/${slug}/todos?include_done=true`, { credentials: "include" });
    if (r.ok && slug === props.project.slug) {
      const all = await r.json() as Todo[];
      doneCount.value = all.filter((t) => t.status === "done").length;
    }
  } catch {
    /* best-effort counter */
  }
}

function relative(iso: string | null): string {
  if (!iso) return "";
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return "just now";
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
  return `${Math.floor(ms / 86_400_000)}d ago`;
}

watch(() => props.project.slug, () => {
  if (typeof localStorage !== "undefined") {
    expanded.value = localStorage.getItem(`vc:card-expanded:todos:${props.project.slug}`) !== "false";
  }
  load();
  refreshDoneCount();
}, { immediate: true });

// Live refresh whenever Claude (or another tab) mutates todos.
onProjectLiveEvent(
  ["todo.created", "todo.batch_created", "todo.updated", "todo.started", "todo.completed", "todo.deleted"],
  () => {
    void load();
    void refreshDoneCount();
  },
);
</script>

<template>
  <section class="glass rounded-lg p-5">
    <header
      class="flex items-center justify-between cursor-pointer select-none"
      :class="{ 'mb-4': expanded }"
      @click="toggle"
    >
      <div class="flex items-center gap-2">
        <span
          class="font-mono text-fg-subtle transition-transform duration-fast"
          :class="{ 'rotate-90': expanded }"
        >▸</span>
        <h3 class="mono-label text-fg-muted">//todos</h3>
      </div>
      <div class="flex items-center gap-3 text-small" @click.stop>
        <span class="text-fg-subtle tabular-nums">
          <span class="text-fg-body font-mono">{{ todos.filter(t => t.status !== 'done').length }}</span>
          open
        </span>
        <span v-if="doneCount > 0" class="text-fg-subtle tabular-nums">
          ·
          <span class="text-signal-green font-mono">{{ doneCount }}</span>
          done
        </span>
        <button
          class="mono-label transition-colors"
          :class="includeDone ? 'text-signal-green' : 'text-fg-subtle hover:text-fg-body'"
          @click.stop="setIncludeDone(!includeDone)"
          :title="includeDone ? 'Hide completed todos' : 'Show completed todos'"
        >{{ includeDone ? '☑ show done' : '☐ show done' }}</button>
      </div>
    </header>

    <div v-if="expanded">
      <!-- Add form -->
      <div class="flex gap-2 mb-2">
        <input
          v-model="newBatch"
          placeholder="batch (optional)"
          class="h-8 px-2 text-small font-mono bg-bg-surface border border-border rounded w-40"
          @keydown.enter="add"
        />
        <input
          v-model="newTitle"
          placeholder="New todo, or a goal for ✨ AI plan — press ⏎"
          class="h-8 px-2 text-small bg-bg-surface border border-border rounded flex-1"
          :disabled="planning"
          @keydown.enter="add"
        />
        <button
          class="h-8 px-3 text-small font-mono bg-signal-green hover:opacity-90 transition-opacity rounded disabled:opacity-50"
          style="color: #070b10"
          :disabled="!newTitle.trim() || planning"
          @click="add"
        >add</button>
        <button
          class="h-8 px-3 text-small font-mono rounded border transition-colors disabled:opacity-50"
          style="border-color: rgba(92,200,164,0.4); color: #5cc8a4; background: rgba(92,200,164,0.06)"
          :disabled="!newTitle.trim() || planning"
          :title="'AI: break this into a batch of todos'"
          @click="aiPlan"
        >{{ planning ? "✨ planning…" : "✨ AI plan" }}</button>
      </div>
      <p
        v-if="planError"
        class="text-[11px] text-signal-red mb-3"
      >{{ planError }}</p>

      <div v-if="loading && todos.length === 0" class="text-fg-subtle mono-label">loading…</div>
      <div
        v-else-if="todos.length === 0"
        class="rounded-md py-6 px-4 text-center"
        style="background: rgba(92,200,164,0.04); border: 1px dashed rgba(92,200,164,0.25)"
      >
        <p class="text-small text-fg-body">Nothing on the list yet.</p>
        <p class="text-[11px] text-fg-subtle mt-1">
          Type a goal above and hit <span class="font-mono">✨ AI plan</span> — Claude breaks it into todos.
        </p>
      </div>

      <div v-else class="space-y-5">
        <div v-for="g in grouped" :key="g.label ?? '__ungrouped__'">
          <!-- Batch header + progress -->
          <header v-if="g.label" class="flex items-center justify-between mb-2">
            <h4 class="mono-label text-fg-body">{{ g.label }}</h4>
            <div class="flex items-center gap-2">
              <div class="w-24 h-1 rounded-full bg-bg-surface overflow-hidden">
                <div
                  class="h-full bg-signal-green transition-all duration-slow"
                  :style="{ width: progressFor(g.items).pct + '%' }"
                />
              </div>
              <span class="font-mono text-[10px] text-fg-subtle tabular-nums">
                {{ progressFor(g.items).done }} / {{ progressFor(g.items).total }}
              </span>
            </div>
          </header>

          <TransitionGroup
            tag="ul"
            name="todo-list"
            class="space-y-1 relative"
          >
            <li
              v-for="t in g.items"
              :key="t.id"
              class="group flex items-start gap-3 py-1.5 px-2 -mx-2 rounded hover:bg-white/[0.03] transition-colors"
              :class="{
                'opacity-55': t.status === 'done',
                'ring-1 ring-signal-green/40 bg-signal-green/[0.04]': t.status === 'in_progress',
              }"
            >
              <!-- Checkbox with bounce-in tick animation on done -->
              <button
                class="mt-0.5 w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-all duration-fast"
                :class="t.status === 'done'
                  ? 'bg-signal-green border-signal-green scale-100 shadow-[0_0_8px_rgba(92,200,164,0.4)]'
                  : 'border-border hover:border-signal-green hover:scale-110'"
                :aria-label="t.status === 'done' ? 'reopen' : 'complete'"
                @click="toggleCompletion(t)"
              >
                <transition
                  enter-active-class="transition-transform duration-med"
                  enter-from-class="scale-0 rotate-45"
                  enter-to-class="scale-100 rotate-0"
                >
                  <svg v-if="t.status === 'done'" width="10" height="10" viewBox="0 0 10 10" fill="none" class="origin-center">
                    <path d="M2 5L4 7L8 3" stroke="#070b10" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </transition>
              </button>

              <!-- Title + metadata -->
              <div class="flex-1 min-w-0">
                <div class="flex items-baseline gap-2 flex-wrap">
                  <span class="text-small text-fg-body" :class="{ 'line-through': t.status === 'done' }">
                    {{ t.title }}
                  </span>
                  <span v-if="t.status === 'in_progress'" class="mono-label text-[10px] text-signal-green">
                    ◉ claude is on this
                  </span>
                  <span v-if="t.completed_by === 'claude'" class="mono-label text-[10px] text-signal-green">
                    ✓ by claude
                  </span>
                  <span v-if="t.completed_at" class="text-[10px] text-fg-subtle ml-auto">
                    {{ relative(t.completed_at) }}
                  </span>
                </div>
                <p
                  v-if="t.completion_note && t.status === 'done'"
                  class="text-[11px] text-fg-subtle mt-0.5 italic"
                >— {{ t.completion_note }}</p>
              </div>

              <!-- Remove -->
              <button
                class="opacity-0 group-hover:opacity-100 text-fg-subtle hover:text-signal-red text-small transition-opacity"
                @click="remove(t)"
                aria-label="delete"
              >✕</button>
            </li>
          </TransitionGroup>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* Smooth enter/leave + reorder when todos move between "open" and "done"
   piles. Uses TransitionGroup which FLIPs existing items when the list
   reorders. */
.todo-list-enter-active,
.todo-list-leave-active,
.todo-list-move {
  transition: all 280ms cubic-bezier(0.2, 0.6, 0.2, 1);
}
.todo-list-enter-from {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}
.todo-list-leave-to {
  opacity: 0;
  transform: translateX(6px);
}
.todo-list-leave-active {
  position: absolute;
  left: 0;
  right: 0;
}
</style>
