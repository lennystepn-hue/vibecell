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

function hostOf(url: string): string {
  return new URL(url).host;
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
