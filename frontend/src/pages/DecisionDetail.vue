<script setup lang="ts">
import { ref, watch } from "vue";
import { useRoute } from "vue-router";

import SidebarProjects from "@/components/app/SidebarProjects.vue";

interface Decision {
  id: string;
  title: string;
  context: string | null;
  decision: string;
  consequences: string | null;
  reconsider_if: string | null;
  created_at: string | null;
}

const route = useRoute();
const decision = ref<Decision | null>(null);
const loading = ref(false);
const err = ref<string | null>(null);

async function load(slug: string, id: string) {
  loading.value = true;
  err.value = null;
  decision.value = null;
  try {
    const r = await fetch(`/api/v1/projects/${slug}/decisions/${id}`, { credentials: "include" });
    if (!r.ok) { err.value = `Error ${r.status}`; return; }
    decision.value = await r.json();
  } catch {
    err.value = "Failed to load decision";
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
</script>

<template>
  <div class="flex h-full">
    <SidebarProjects />
    <div class="flex-1 overflow-y-auto">
      <div class="max-w-3xl mx-auto px-4 sm:px-8 py-6 sm:py-8">
        <nav class="mb-6 text-small">
          <RouterLink :to="`/p/${route.params.slug}`" class="text-fg-muted hover:text-fg-body transition-colors">
            ← Back to {{ route.params.slug }}
          </RouterLink>
        </nav>

        <div v-if="loading" class="text-fg-muted mono-label">loading…</div>
        <div v-else-if="err" class="glass rounded-lg p-4 border border-signal-red/40 text-signal-red">{{ err }}</div>
        <div v-else-if="decision">
          <header class="mb-6">
            <p class="mono-label text-signal-amber">// decision (ADR)</p>
            <h1 class="text-display text-fg-primary tracking-tight mt-1">{{ decision.title }}</h1>
            <p class="mono-label text-fg-subtle mt-2">Recorded {{ fmtTime(decision.created_at) }}</p>
          </header>

          <section v-if="decision.context" class="glass rounded-lg p-5 mb-4">
            <h3 class="mono-label text-fg-muted mb-2">//context</h3>
            <p class="text-body text-fg-body whitespace-pre-wrap leading-relaxed">{{ decision.context }}</p>
          </section>

          <section class="glass rounded-lg p-5 mb-4" style="border-color: rgba(245,184,74,0.25)">
            <h3 class="mono-label text-signal-amber mb-2">//decision</h3>
            <p class="text-body text-fg-primary whitespace-pre-wrap leading-relaxed">{{ decision.decision }}</p>
          </section>

          <section v-if="decision.consequences" class="glass rounded-lg p-5 mb-4">
            <h3 class="mono-label text-fg-muted mb-2">//consequences</h3>
            <p class="text-body text-fg-body whitespace-pre-wrap leading-relaxed">{{ decision.consequences }}</p>
          </section>

          <section v-if="decision.reconsider_if" class="glass rounded-lg p-5 mb-4">
            <h3 class="mono-label text-fg-muted mb-2">//reconsider-if</h3>
            <p class="text-body text-fg-body whitespace-pre-wrap leading-relaxed">{{ decision.reconsider_if }}</p>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>
