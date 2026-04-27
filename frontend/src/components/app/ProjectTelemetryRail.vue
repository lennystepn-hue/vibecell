<script setup lang="ts">
import { onMounted, ref, watch } from "vue";

import DataRow from "@/components/ui/DataRow.vue";
import MonoLabel from "@/components/ui/MonoLabel.vue";
import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
type LifecycleEventOut = components["schemas"]["LifecycleEventOut"];

const props = defineProps<{ project: Project }>();

const events = ref<LifecycleEventOut[]>([]);

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toISOString().slice(0, 10);
}

function hostOf(url: string): string {
  return new URL(url).host;
}

function kindIcon(kind: string): string {
  // Cockpit marks — geometric, not pictographic. Replace earlier emoji
  // set per the impeccable design brief.
  if (kind.startsWith("ship")) return "↑";
  if (kind.startsWith("launch")) return "◢";
  if (kind.startsWith("decision")) return "◇";
  if (kind.startsWith("session")) return "◉";
  if (kind.startsWith("idea")) return "◌";
  if (kind.startsWith("note")) return "▤";
  return "·";
}

function detailSnippet(ev: LifecycleEventOut): string {
  if (!ev.detail) return "";
  if (typeof ev.detail === "object") {
    const d = ev.detail as Record<string, unknown>;
    const preferred = ["title", "version", "summary", "platform", "body"];
    for (const k of preferred) {
      const v = d[k];
      if (typeof v === "string" && v.length > 0) return v.slice(0, 40);
    }
  }
  return "";
}

async function fetchEvents() {
  const { data } = await api.GET("/api/v1/projects/{slug}/lifecycle-events", {
    params: { path: { slug: props.project.slug } },
  });
  // Newest first, top 5.
  events.value = (data ?? [])
    .slice()
    .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
    .slice(0, 5);
}

onMounted(fetchEvents);
watch(() => props.project.slug, fetchEvents);
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
              >{{ hostOf(e.url) }}</a>
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

      <section v-if="events.length > 0">
        <MonoLabel>lifecycle</MonoLabel>
        <ul class="mt-2 space-y-1">
          <li
            v-for="ev in events"
            :key="ev.id"
            class="flex items-start gap-2 text-[11px]"
          >
            <span aria-hidden="true" class="shrink-0">{{ kindIcon(ev.kind) }}</span>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <span class="font-mono text-[10px] text-fg-subtle">{{ formatDate(ev.at) }}</span>
                <span
                  class="font-mono text-[9px] uppercase tracking-wider px-1 py-0.5 rounded-sm"
                  :style="{ background: 'var(--signal-blue-bg)', color: 'var(--fg-body)' }"
                >{{ ev.kind }}</span>
              </div>
              <p v-if="detailSnippet(ev)" class="text-fg-body truncate mt-0.5">{{ detailSnippet(ev) }}</p>
            </div>
          </li>
        </ul>
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
