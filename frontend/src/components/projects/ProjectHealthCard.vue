<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { onProjectLiveEvent } from "@/composables/useProjectLive";

const props = defineProps<{ slug: string }>();

type HealthStatus = "up" | "down" | "timeout" | "error" | "unknown" | "not_configured" | "not_probed_yet" | string;

/** Raw shape of GET /api/v1/projects/{slug}/health — matches the backend.
 *  The backend uses `last_status` / `avg_latency_ms_24h` for the persisted
 *  row, and `status` for the ephemeral "not_configured" / "not_probed_yet"
 *  pending states. We unify both into `derivedStatus` below.
 */
interface HealthPayload {
  project_id: string;
  slug: string;
  // Pending / meta state
  status?: HealthStatus;
  message?: string;
  healthcheck_url?: string;
  // Persisted summary fields
  last_status?: HealthStatus;
  last_probed_at?: string | null;
  uptime_24h_pct?: number | null;
  uptime_7d_pct?: number | null;
  avg_latency_ms_24h?: number | null;
  events_last_24h?: Array<{ probed_at: string; status: string; http_code: number | null; latency_ms: number | null }>;
}

const health = ref<HealthPayload | null>(null);
const loading = ref(true);
const fetchError = ref<string | null>(null);

async function load(slug: string) {
  loading.value = true;
  fetchError.value = null;
  health.value = null;
  try {
    const res = await fetch(`/api/v1/projects/${slug}/health`, { credentials: "include" });
    if (slug !== props.slug) return;
    if (res.ok) {
      health.value = await res.json();
    } else if (res.status === 501) {
      health.value = { project_id: "", slug, status: "not_configured" };
    } else {
      fetchError.value = `Error ${res.status}`;
    }
  } catch {
    if (slug === props.slug) fetchError.value = "Failed to load health data";
  } finally {
    if (slug === props.slug) loading.value = false;
  }
}

watch(() => props.slug, (slug) => void load(slug), { immediate: true });
// Live-refresh whenever anything happens on the project (we don't emit a
// health-specific event yet, so use the wildcard — health is cheap to refetch).
onProjectLiveEvent("*", () => void load(props.slug));

// ---- Normalised view ----
const derivedStatus = computed<HealthStatus>(
  () => health.value?.last_status ?? health.value?.status ?? "unknown",
);
const lastProbedAt = computed(() => health.value?.last_probed_at ?? null);
const latencyMs = computed(() => health.value?.avg_latency_ms_24h ?? null);
const uptime24 = computed(() => health.value?.uptime_24h_pct ?? null);
const uptime7d = computed(() => health.value?.uptime_7d_pct ?? null);
const message = computed(() => health.value?.message ?? null);

const hasPersistedData = computed(() => {
  if (!health.value) return false;
  return health.value.last_status !== undefined && health.value.last_status !== null;
});

const prettyStatus: Record<string, string> = {
  up: "up",
  down: "down",
  timeout: "timeout",
  error: "error",
  unknown: "unknown",
  not_configured: "not configured",
  not_probed_yet: "waiting for first probe",
};

function statusLabel(s: HealthStatus): string {
  return prettyStatus[s] ?? s;
}

function statusColor(s: HealthStatus): string {
  switch (s) {
    case "up": return "var(--signal-green)";
    case "down": return "var(--signal-red)";
    case "timeout":
    case "error": return "var(--signal-amber, #f59e0b)";
    default: return "var(--fg-subtle)";
  }
}

function statusBg(s: HealthStatus): string {
  switch (s) {
    case "up": return "rgba(92,200,164,0.12)";
    case "down": return "rgba(229,101,101,0.12)";
    case "timeout":
    case "error": return "rgba(245,158,11,0.12)";
    default: return "rgba(138,180,255,0.06)";
  }
}

function formatTime(iso: string | null | undefined): string {
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

function formatPct(pct: number | null | undefined): string {
  if (pct === undefined || pct === null) return "—";
  return `${Number(pct).toFixed(1)}%`;
}

function formatLatency(ms: number | null | undefined): string {
  if (ms === undefined || ms === null) return "—";
  return `${Math.round(ms)}ms`;
}

// Tiny 24h sparkline of the last probe events (one bar per event).
const sparkline = computed(() => {
  const events = health.value?.events_last_24h ?? [];
  // Oldest first left-to-right.
  return [...events].reverse().map((e) => ({
    status: e.status,
    latency: e.latency_ms,
  }));
});
</script>

<template>
  <section class="glass rounded-lg p-5">
    <header class="flex items-center justify-between mb-3">
      <h3 class="mono-label text-fg-muted">//health</h3>
      <span v-if="lastProbedAt" class="text-small text-fg-subtle tabular-nums">
        {{ formatTime(lastProbedAt) }}
      </span>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="text-small text-fg-subtle font-mono">probing…</div>

    <!-- Fetch error -->
    <div v-else-if="fetchError" class="text-small text-signal-red">{{ fetchError }}</div>

    <!-- Not configured -->
    <div v-else-if="derivedStatus === 'not_configured'" class="space-y-1">
      <p class="text-small text-fg-muted">No healthcheck URL configured.</p>
      <p class="text-small text-fg-subtle">
        Add a link of kind <span class="font-mono">healthcheck</span> to enable uptime monitoring.
      </p>
    </div>

    <!-- Waiting for first probe (link exists but no summary yet) -->
    <div v-else-if="derivedStatus === 'not_probed_yet' || (!hasPersistedData && derivedStatus === 'unknown')" class="flex items-center gap-3">
      <span class="relative inline-flex w-2 h-2" aria-hidden="true">
        <span class="absolute inset-0 rounded-full bg-fg-subtle opacity-60 animate-ping" />
        <span class="relative inline-flex w-full h-full rounded-full bg-fg-subtle" />
      </span>
      <div class="min-w-0">
        <p class="text-small text-fg-body">Waiting for first probe</p>
        <p class="text-[11px] text-fg-subtle mt-0.5">{{ message ?? 'Runs every 5 minutes.' }}</p>
      </div>
    </div>

    <!-- Persisted data -->
    <div v-else-if="health" class="space-y-4">
      <!-- Status row: big dot + status pill -->
      <div class="flex items-center gap-3">
        <span
          class="inline-flex w-2.5 h-2.5 rounded-full shrink-0"
          :style="{ background: statusColor(derivedStatus), boxShadow: `0 0 10px ${statusColor(derivedStatus)}` }"
        />
        <span
          class="mono-label px-2 py-0.5 rounded text-[11px]"
          :style="{ background: statusBg(derivedStatus), color: statusColor(derivedStatus) }"
        >{{ statusLabel(derivedStatus) }}</span>
      </div>

      <!-- Stats grid -->
      <div class="grid grid-cols-3 gap-3">
        <div>
          <p class="font-mono text-[10px] uppercase tracking-[0.12em] text-fg-subtle">24h uptime</p>
          <p class="font-mono text-title text-fg-primary tabular-nums" :style="{ color: statusColor(derivedStatus) }">
            {{ formatPct(uptime24) }}
          </p>
        </div>
        <div>
          <p class="font-mono text-[10px] uppercase tracking-[0.12em] text-fg-subtle">7d uptime</p>
          <p class="font-mono text-title text-fg-body tabular-nums">{{ formatPct(uptime7d) }}</p>
        </div>
        <div>
          <p class="font-mono text-[10px] uppercase tracking-[0.12em] text-fg-subtle">latency</p>
          <p class="font-mono text-title text-fg-body tabular-nums">{{ formatLatency(latencyMs) }}</p>
        </div>
      </div>

      <!-- Sparkline: last 24 probes, 3px each, color-coded. -->
      <div v-if="sparkline.length > 0">
        <p class="font-mono text-[10px] uppercase tracking-[0.12em] text-fg-subtle mb-1.5">
          last {{ sparkline.length }} probes
        </p>
        <div class="flex items-end gap-[2px] h-6">
          <span
            v-for="(e, idx) in sparkline"
            :key="idx"
            class="w-[4px] rounded-sm"
            :style="{
              height: (e.status === 'up' ? '100%' : '40%'),
              background: statusColor(e.status),
              opacity: e.status === 'up' ? 0.85 : 1,
            }"
            :title="`${e.status}${e.latency ? ` · ${e.latency}ms` : ''}`"
          />
        </div>
      </div>
    </div>
  </section>
</template>
