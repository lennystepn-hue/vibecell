<script setup lang="ts">
import { ref, watch } from "vue";
import { useRoute } from "vue-router";

import SidebarProjects from "@/components/app/SidebarProjects.vue";

interface Session {
  id: string;
  started_at: string;
  ended_at: string | null;
  summary: string;
  files_touched: string[];
  commits: Array<{ sha?: string; msg?: string; message?: string }>;
  next_step: string | null;
  source: string | null;
}

const route = useRoute();
const session = ref<Session | null>(null);
const loading = ref(false);
const err = ref<string | null>(null);

async function load(slug: string, id: string) {
  loading.value = true;
  err.value = null;
  session.value = null;
  try {
    const r = await fetch(`/api/v1/projects/${slug}/sessions/${id}`, { credentials: "include" });
    if (!r.ok) {
      err.value = `Error ${r.status}`;
      return;
    }
    session.value = await r.json();
  } catch {
    err.value = "Failed to load session";
  } finally {
    loading.value = false;
  }
}

watch(
  () => [route.params.slug, route.params.id],
  ([slug, id]) => {
    if (typeof slug === "string" && typeof id === "string") load(slug, id);
  },
  { immediate: true },
);

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function fmtRel(iso: string | null): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return "just now";
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
  return `${Math.floor(ms / 86_400_000)}d ago`;
}
</script>

<template>
  <div class="flex h-full">
    <SidebarProjects />
    <div class="flex-1 overflow-y-auto">
      <div class="max-w-3xl mx-auto px-8 py-8">
        <nav class="mb-6 text-small">
          <RouterLink :to="`/p/${route.params.slug}`" class="text-fg-muted hover:text-fg-body transition-colors">
            ← Back to {{ route.params.slug }}
          </RouterLink>
        </nav>

        <div v-if="loading" class="text-fg-muted mono-label">loading…</div>
        <div v-else-if="err" class="glass rounded-lg p-4 border border-signal-red/40 text-signal-red">{{ err }}</div>
        <div v-else-if="session">
          <header class="mb-6">
            <p class="mono-label text-signal-green">// session</p>
            <h1 class="text-display text-fg-primary tracking-tight mt-1">{{ session.summary.split('.')[0] }}</h1>
            <div class="flex items-center gap-3 mt-2 text-small text-fg-muted flex-wrap">
              <span class="mono-label">Started {{ fmtTime(session.started_at) }} · {{ fmtRel(session.started_at) }}</span>
              <span v-if="session.source" class="mono-label">via {{ session.source }}</span>
            </div>
          </header>

          <section class="glass rounded-lg p-5 mb-4">
            <h3 class="mono-label text-fg-muted mb-2">//summary</h3>
            <p class="text-body text-fg-body whitespace-pre-wrap leading-relaxed">{{ session.summary }}</p>
          </section>

          <section v-if="session.next_step" class="glass rounded-lg p-5 mb-4">
            <h3 class="mono-label text-fg-muted mb-2">//next-step</h3>
            <p class="text-body text-fg-body whitespace-pre-wrap">{{ session.next_step }}</p>
          </section>

          <section v-if="session.files_touched && session.files_touched.length" class="glass rounded-lg p-5 mb-4">
            <h3 class="mono-label text-fg-muted mb-2">//files-touched · {{ session.files_touched.length }}</h3>
            <ul class="space-y-1">
              <li
                v-for="f in session.files_touched"
                :key="f"
                class="font-mono text-small text-fg-body truncate"
              >{{ f }}</li>
            </ul>
          </section>

          <section v-if="session.commits && session.commits.length" class="glass rounded-lg p-5 mb-4">
            <h3 class="mono-label text-fg-muted mb-2">//commits · {{ session.commits.length }}</h3>
            <ul class="space-y-2">
              <li v-for="(c, i) in session.commits" :key="i" class="flex gap-3 items-baseline">
                <code v-if="c.sha" class="font-mono text-small text-signal-green shrink-0">{{ String(c.sha).slice(0, 7) }}</code>
                <span class="text-small text-fg-body">{{ c.msg || c.message }}</span>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>
