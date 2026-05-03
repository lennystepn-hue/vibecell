<script setup lang="ts">
/**
 * /admin/system — extended system health. Reuses the same /system-health
 * endpoint as the Overview but with all rows visible at full size +
 * the public /api/v1/status payload mirrored alongside.
 */
import { onBeforeUnmount, onMounted, ref } from "vue";

interface HealthRow { label: string; value: string; accent?: string | null }
interface SystemHealth { rows: HealthRow[]; generated_at: string }
interface PublicStatus {
  overall: "ok" | "degraded" | "down";
  components: { name: string; status: string; latency_ms: number | null; message: string | null }[];
  generated_at: string;
  git_sha: string;
  version: string;
}

const health = ref<SystemHealth | null>(null);
const publicStatus = ref<PublicStatus | null>(null);
const refreshHandle = ref<ReturnType<typeof setInterval> | null>(null);

async function load() {
  await Promise.all([
    fetch("/api/v1/admin/system-health", { credentials: "include" })
      .then((r) => r.ok ? r.json() : null)
      .then((d: SystemHealth | null) => { if (d) health.value = d; }),
    fetch("/api/v1/status")
      .then((r) => r.ok ? r.json() : null)
      .then((d: PublicStatus | null) => { if (d) publicStatus.value = d; }),
  ]);
}

onMounted(async () => {
  await load();
  refreshHandle.value = setInterval(load, 30000);
});
onBeforeUnmount(() => {
  if (refreshHandle.value) clearInterval(refreshHandle.value);
});

function fmtRel(iso: string | null | undefined): string {
  if (!iso) return "—";
  const min = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}
function accentStyle(s?: string | null): Record<string, string> {
  if (s === "green" || s === "ok") return { color: "var(--signal-green)" };
  if (s === "amber" || s === "degraded") return { color: "var(--signal-amber, #f59e0b)" };
  if (s === "red" || s === "down") return { color: "var(--signal-red)" };
  return { color: "var(--fg-primary)" };
}
</script>

<template>
  <div class="max-w-[900px] mx-auto px-4 sm:px-8 py-6 sm:py-8">
    <header class="mb-6">
      <p class="font-mono text-[11px] uppercase tracking-[0.15em] text-signal-green mb-1">// admin · system</p>
      <h1 class="text-display text-fg-primary tracking-tight">System health</h1>
      <p class="text-body text-fg-muted mt-1">DB, Redis, cron heartbeats, public-status mirror.</p>
    </header>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <section class="glass rounded-lg p-5">
        <header class="flex items-center justify-between mb-3">
          <h3 class="mono-label text-fg-muted">// admin probes</h3>
          <span v-if="health" class="font-mono text-[10px] text-fg-subtle">{{ fmtRel(health.generated_at) }}</span>
        </header>
        <div v-if="health" class="space-y-2">
          <div
            v-for="row in health.rows"
            :key="row.label"
            class="flex items-center justify-between text-small"
          >
            <span class="font-mono text-fg-subtle">{{ row.label }}</span>
            <span class="font-mono tabular-nums" :style="accentStyle(row.accent)">{{ row.value }}</span>
          </div>
        </div>
        <div v-else class="text-small text-fg-subtle font-mono">loading…</div>
      </section>

      <section class="glass rounded-lg p-5">
        <header class="flex items-center justify-between mb-3">
          <h3 class="mono-label text-fg-muted">// public /api/v1/status</h3>
          <span
            v-if="publicStatus"
            class="font-mono text-small uppercase tracking-[0.1em]"
            :style="accentStyle(publicStatus.overall)"
          >{{ publicStatus.overall }}</span>
        </header>
        <div v-if="publicStatus" class="space-y-2">
          <div
            v-for="c in publicStatus.components"
            :key="c.name"
            class="flex items-center justify-between text-small"
          >
            <span class="font-mono text-fg-subtle">{{ c.name }}</span>
            <span class="font-mono text-[11px]" :style="accentStyle(c.status)">
              {{ c.status }}{{ c.latency_ms !== null ? ` · ${c.latency_ms}ms` : "" }}
            </span>
          </div>
          <p class="font-mono text-[10px] text-fg-subtle mt-3 pt-3 border-t border-border-subtle">
            build {{ publicStatus.git_sha.slice(0, 7) }} · v{{ publicStatus.version }}
          </p>
        </div>
        <div v-else class="text-small text-fg-subtle font-mono">loading…</div>
      </section>
    </div>
  </div>
</template>
