<script setup lang="ts">
import { computed, ref, watch, nextTick } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import { api } from "@/api/client";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
type StackItem = components["schemas"]["StackItemOut"];
const props = defineProps<{ project: Project }>();

const projects = useProjectsStore();
const toast = useToastStore();

const query = ref("");
const results = ref<StackItem[]>([]);
const highlightedIndex = ref(0);
const searching = ref(false);
const adding = ref(false);
const inputRef = ref<HTMLInputElement | null>(null);

const attachedSlugs = computed(() => new Set(props.project.stack.map((s) => s.stack_item_slug)));
const filteredResults = computed(() => results.value.filter((r) => !attachedSlugs.value.has(r.slug)));

function openAdding() {
  adding.value = true;
  nextTick(() => inputRef.value?.focus());
}

function cancelAdding() {
  adding.value = false;
  query.value = "";
  results.value = [];
}

let searchTimer: ReturnType<typeof setTimeout> | null = null;
watch(query, (q) => {
  if (searchTimer) clearTimeout(searchTimer);
  if (!q.trim()) {
    results.value = [];
    return;
  }
  searchTimer = setTimeout(async () => {
    searching.value = true;
    const { data } = await api.GET("/api/v1/stack-items", {
      params: { query: { q, limit: 10 } },
    });
    searching.value = false;
    results.value = data ?? [];
    highlightedIndex.value = 0;
  }, 150);
});

async function attach(item: StackItem) {
  const { error } = await api.POST("/api/v1/projects/{slug}/stack", {
    params: { path: { slug: props.project.slug } },
    body: { stack_item_slug: item.slug, role: null },
  });
  if (error) {
    toast.push(`Couldn't attach ${item.slug}`, "error");
    return;
  }
  query.value = "";
  results.value = [];
  adding.value = false;
  await projects.fetchProject(props.project.slug);
}

async function detach(slug: string) {
  const { error } = await api.DELETE("/api/v1/projects/{slug}/stack/{stack_item_slug}", {
    params: { path: { slug: props.project.slug, stack_item_slug: slug } },
  });
  if (error) {
    toast.push(`Couldn't remove ${slug}`, "error");
    return;
  }
  await projects.fetchProject(props.project.slug);
}
</script>

<template>
  <section class="glass rounded-lg p-5">
    <MonoLabel>stack</MonoLabel>

    <div class="flex flex-wrap gap-2 mt-3">
      <span
        v-for="s in project.stack"
        :key="s.stack_item_slug"
        class="group inline-flex items-center gap-1.5 px-2.5 h-6 rounded-sm font-mono text-[11px]"
        :style="{ background: 'var(--signal-blue-bg)', color: 'var(--fg-body)', border: '1px solid var(--border-subtle)' }"
      >
        {{ s.name }}
        <button
          type="button"
          class="opacity-0 group-hover:opacity-100 text-fg-subtle hover:text-signal-red transition-all"
          aria-label="Detach"
          @click="detach(s.stack_item_slug)"
        >✕</button>
      </span>
    </div>

    <!-- Inline add row (shown only when adding) -->
    <div v-if="adding" class="relative mt-3">
      <input
        ref="inputRef"
        v-model="query"
        type="text"
        placeholder="framework, service, model…"
        class="w-full h-9 px-3 rounded-md font-sans text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
        @keydown.esc="cancelAdding"
      />
      <div
        v-if="filteredResults.length > 0"
        class="absolute left-0 right-0 top-full mt-1 glass rounded-md overflow-hidden z-10 max-h-60 overflow-y-auto"
        style="background: rgba(13, 18, 26, 0.95)"
      >
        <button
          v-for="(item, i) in filteredResults"
          :key="item.slug"
          type="button"
          :class="[
            'w-full px-3 py-1.5 text-left flex items-center justify-between gap-3',
            i === highlightedIndex ? 'bg-bg-surface-hi' : 'hover:bg-bg-surface/60',
          ]"
          @click="attach(item)"
          @mouseenter="highlightedIndex = i"
        >
          <span>{{ item.name }}</span>
          <span class="mono text-[10px] text-fg-muted">{{ item.kind ?? "—" }}</span>
        </button>
      </div>
    </div>

    <!-- Trigger button (hidden when adding) -->
    <button
      v-else
      type="button"
      class="mt-3 mono-label text-fg-subtle hover:text-fg-body transition-colors"
      @click="openAdding"
    >+ add stack item</button>
  </section>
</template>
