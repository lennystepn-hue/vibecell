<script setup lang="ts">
import { ref, watch } from "vue";
import MonoLabel from "@/components/ui/MonoLabel.vue";

const props = defineProps<{ slug: string }>();

type HealthStatus = "up" | "down" | "timeout" | "error" | "unknown" | "not_configured" | string;

interface HealthSummary {
  project_id: string;
  status: HealthStatus;
  last_probed_at?: string;
  latency_ms?: number;
  uptime_24h_pct?: number;
  uptime_7d_pct?: number;
  avg_latency_ms?: number;
  message?: string;
  healthcheck_url?: string;
}

const health = ref<HealthSummary | null>(null);
const loading = ref(true);
const fetchError = ref<string | null>(null);

async function load(slug: string) {
  loading.value = true;
  fetchError.value = null;
  health.value = null;  // clear stale data before the new fetch resolves
  try {
    const res = await fetch(`/api/v1/projects/${slug}/health`, { credentials: "include" });
    if (slug !== props.slug) return;  // stale response — user already moved to another project
    if (res.ok) {
      health.value = await res.json();
    } else if (res.status === 501) {
      health.value = { project_id: "", status: "not_configured", message: "" };
    } else {
      fetchError.value = `Error ${res.status}`;
    }
  } catch (e) {
    if (slug === props.slug) fetchError.value = "Failed to load health data";
  } finally {
    if (slug === props.slug) loading.value = false;
  }
}

// Re-fetch whenever the slug prop changes so cached state from the previous
// project never bleeds into the next one.
watch(() => props.slug, (slug) => void load(slug), { immediate: true });

function trafficLightColor(status: HealthStatus): string {
  switch (status) {
    case "up": return "var(--signal-green)";
    case "down": return "var(--signal-red)";
    case "timeout":
    case "error": return "var(--signal-amber, #f59e0b)";
    default: return "var(--fg-subtle)";
  }
}

function trafficLightBg(status: HealthStatus): string {
  switch (status) {
    case "up": return "var(--signal-green-bg)";
    case "down": return "var(--signal-red-bg)";
    case "timeout":
    case "error": return "rgba(245, 158, 11, 0.1)";
    default: return "var(--bg-elevated)";
  }
}

function formatTime(iso: string | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h ago`;
  return `${Math.floor(diffH / 24)}d ago`;
}

function formatPct(pct: number | undefined): string {
  if (pct === undefined || pct === null) return "—";
  return `${pct.toFixed(1)}%`;
}
</script>

<template>
  <section class="glass rounded-lg p-5">
    <MonoLabel>health</MonoLabel>

    <!-- Loading -->
    <div v-if="loading" class="mt-3 text-small text-fg-subtle font-mono">probing…</div>

    <!-- Error -->
    <div v-else-if="fetchError" class="mt-3 text-small text-signal-red">{{ fetchError }}</div>

    <!-- Not configured -->
    <div v-else-if="health?.status === 'not_configured'" class="mt-3">
      <p class="text-small text-fg-muted">No healthcheck URL configured.</p>
      <p class="text-small text-fg-subtle mt-1">
        Add a link with kind <span class="font-mono">healthcheck</span> to enable uptime monitoring.
      </p>
    </div>

    <!-- Health data -->
    <div v-else-if="health" class="mt-3 space-y-3">
      <!-- Status indicator -->
      <div class="flex items-center gap-3">
        <div
          class="w-3 h-3 rounded-full shrink-0"
          :style="{ background: trafficLightColor(health.status) }"
        />
        <div
          class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-small font-mono"
          :style="{ background: trafficLightBg(health.status), color: trafficLightColor(health.status) }"
        >
          {{ health.status === 'not_configured' ? 'not configured' : health.status }}
        </div>
        <span v-if="health.last_probed_at" class="text-small text-fg-subtle ml-auto">
          {{ formatTime(health.last_probed_at) }}
        </span>
      </div>

      <!-- Latency -->
      <div v-if="health.avg_latency_ms !== undefined && health.avg_latency_ms !== null" class="flex gap-4">
        <div>
          <p class="font-mono text-[10px] text-fg-subtle uppercase tracking-widest">latency</p>
          <p class="text-small text-fg-body font-mono">{{ health.avg_latency_ms }}ms avg</p>
        </div>
        <div v-if="health.uptime_24h_pct !== undefined">
          <p class="font-mono text-[10px] text-fg-subtle uppercase tracking-widest">24h uptime</p>
          <p class="text-small text-fg-body font-mono">{{ formatPct(health.uptime_24h_pct) }}</p>
        </div>
        <div v-if="health.uptime_7d_pct !== undefined">
          <p class="font-mono text-[10px] text-fg-subtle uppercase tracking-widest">7d uptime</p>
          <p class="text-small text-fg-body font-mono">{{ formatPct(health.uptime_7d_pct) }}</p>
        </div>
      </div>

      <!-- Message for unknown/pending state -->
      <p v-if="health.status === 'unknown'" class="text-small text-fg-muted italic">
        No probes yet — healthcheck will run within 5 minutes.
      </p>
      <p v-else-if="health.message && !['up','down','timeout','error'].includes(health.status)" class="text-small text-fg-muted italic">
        {{ health.message }}
      </p>
    </div>
  </section>
</template>
