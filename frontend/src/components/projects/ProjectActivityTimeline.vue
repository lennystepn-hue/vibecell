<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
void RouterLink;  // tell the template compiler RouterLink is in scope for dynamic :is usage

interface ActivityEvent {
  type: "session" | "decision" | "idea" | "ship" | "lifecycle" | "note" | "tool_call";
  at: string | null;
  title: string;
  body: string | null;
  meta: Record<string, any>;
}

const props = defineProps<{ projectSlug: string }>();

const events = ref<ActivityEvent[]>([]);
const loading = ref(false);
const expanded = ref<boolean>(true);
let pollId: ReturnType<typeof setInterval> | null = null;

function toggle() {
  expanded.value = !expanded.value;
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(`vc:activity-expanded:${props.projectSlug}`, expanded.value ? "true" : "false");
  }
}

async function load() {
  const slug = props.projectSlug;
  loading.value = true;
  try {
    const r = await fetch(`/api/v1/projects/${slug}/activity?limit=100`, {
      credentials: "include",
    });
    // Only commit if we're still looking at the same project.
    if (r.ok && slug === props.projectSlug) events.value = await r.json();
  } finally {
    if (slug === props.projectSlug) loading.value = false;
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

function iconFor(type: string) {
  return ({
    session: "◎",
    decision: "⟁",
    idea: "✦",
    ship: "▲",
    lifecycle: "•",
    note: "✎",
    tool_call: "→",
  } as any)[type] ?? "•";
}

function colorFor(type: string) {
  return ({
    session: "text-signal-green",
    decision: "text-signal-amber",
    idea: "text-fg-body",
    ship: "text-signal-green",
    lifecycle: "text-fg-subtle",
    note: "text-fg-muted",
    tool_call: "text-fg-subtle",
  } as any)[type] ?? "text-fg-muted";
}

function linkFor(e: ActivityEvent): string | null {
  const id = e.meta?.id;
  if (!id) return null;
  if (e.type === "session") return `/p/${props.projectSlug}/sessions/${id}`;
  if (e.type === "decision") return `/p/${props.projectSlug}/decisions/${id}`;
  return null;
}

// Collapse consecutive tool_call events with the same tool name into a single row
const collapsed = computed(() => {
  const out: (ActivityEvent & { collapsed_count?: number })[] = [];
  for (const e of events.value) {
    const last = out[out.length - 1];
    if (
      e.type === "tool_call" &&
      last &&
      last.type === "tool_call" &&
      last.title === e.title
    ) {
      last.collapsed_count = (last.collapsed_count || 1) + 1;
    } else {
      out.push({ ...e });
    }
  }
  return out;
});

// Reset + reload when the project slug changes (Vue may reuse the component
// across /projects/:slug routes; without this watch, the previous project's
// events would stay visible).
watch(
  () => props.projectSlug,
  (slug) => {
    if (typeof localStorage !== "undefined") {
      expanded.value = localStorage.getItem(`vc:activity-expanded:${slug}`) !== "false";
    }
    events.value = [];
    if (pollId) clearInterval(pollId);
    load();
    pollId = setInterval(load, 15_000);
  },
  { immediate: true },
);
onUnmounted(() => {
  if (pollId) clearInterval(pollId);
});
</script>

<template>
  <section class="glass rounded-lg p-5">
    <header
      class="flex items-center justify-between cursor-pointer select-none"
      :class="{ 'mb-3': expanded }"
      @click="toggle"
    >
      <div class="flex items-center gap-2">
        <span
          class="font-mono text-fg-subtle transition-transform duration-fast"
          :class="{ 'rotate-90': expanded }"
          aria-hidden="true"
        >▸</span>
        <h3 class="mono-label text-fg-muted">//activity</h3>
      </div>
      <span class="text-small text-fg-subtle">{{ events.length }} events · live</span>
    </header>

    <div v-if="expanded">
    <div v-if="loading && events.length === 0" class="text-fg-subtle mono-label text-small">
      loading…
    </div>
    <div v-else-if="events.length === 0" class="text-fg-subtle text-small py-3">
      No activity yet. When Claude logs a session or makes a decision, it shows up here.
    </div>

    <ol
      v-else
      class="space-y-0 relative pl-4 before:content-[''] before:absolute before:left-1 before:top-1 before:bottom-1 before:w-px before:bg-border"
    >
      <component
        :is="linkFor(e) ? 'RouterLink' : 'li'"
        v-for="(e, idx) in collapsed"
        :key="idx"
        :to="linkFor(e) || undefined"
        class="relative py-2.5 flex items-start gap-3 rounded-md -mx-2 px-2 transition-colors"
        :class="linkFor(e) ? 'cursor-pointer hover:bg-white/[0.03]' : ''"
      >
        <span
          class="absolute -left-1 top-3 w-2.5 h-2.5 rounded-full bg-bg-surface border border-border flex items-center justify-center font-mono text-[9px]"
          :class="colorFor(e.type)"
        >{{ iconFor(e.type) }}</span>
        <div class="flex-1 min-w-0">
          <div class="flex items-baseline gap-2 flex-wrap">
            <span class="mono-label text-small" :class="colorFor(e.type)">{{ e.type }}</span>
            <span class="text-small text-fg-body truncate">{{ e.title }}</span>
            <span v-if="e.collapsed_count" class="text-small text-fg-subtle">
              ×{{ e.collapsed_count }}
            </span>
            <span class="ml-auto text-small text-fg-subtle tabular-nums">{{ relative(e.at) }}</span>
          </div>
          <p
            v-if="e.body && e.type !== 'tool_call'"
            class="text-small text-fg-muted mt-1 line-clamp-2"
          >{{ e.body }}</p>
        </div>
      </component>
    </ol>
    </div>
  </section>
</template>
