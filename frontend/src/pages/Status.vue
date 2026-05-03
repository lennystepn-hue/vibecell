<script setup lang="ts">
/**
 * Public status page — anonymous-accessible mirror of /api/v1/status.
 *
 * Polls every 30s. Designed to render fast even during partial outages:
 * components render individually, so a single "down" probe doesn't blank the
 * whole page. The "overall" header uses signal-green / amber / red mapped
 * straight off the API verdict.
 *
 * Routed at both /status (canonical) and as the only page on
 * status.vibecell.dev once Caddy / Cloudflare DNS is wired.
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import { useRouteMeta } from "@/composables/useMeta";

useRouteMeta({
  title: "Status — Vibecell · live system health",
  description:
    "Real-time status of vibecell.dev — API, database, cache, MCP server, billing webhooks, GitHub commit-sync. Auto-refresh every 30 seconds.",
  canonical: "https://vibecell.dev/status",
});

type ComponentStatus = "ok" | "degraded" | "down";

interface StatusComponent {
  name: string;
  status: ComponentStatus;
  latency_ms: number | null;
  message: string | null;
}

interface StatusPayload {
  overall: ComponentStatus;
  components: StatusComponent[];
  incidents: unknown[];
  version: string;
  git_sha: string;
  generated_at: string;
}

const data = ref<StatusPayload | null>(null);
const loading = ref(true);
const fetchError = ref<string | null>(null);
const refreshHandle = ref<ReturnType<typeof setInterval> | null>(null);

async function fetchStatus() {
  fetchError.value = null;
  try {
    const res = await fetch("/api/v1/status", { credentials: "omit" });
    if (!res.ok) {
      fetchError.value = `HTTP ${res.status}`;
      return;
    }
    data.value = (await res.json()) as StatusPayload;
  } catch (e) {
    fetchError.value = e instanceof Error ? e.message : "Network error";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void fetchStatus();
  refreshHandle.value = setInterval(fetchStatus, 30000);
});
onBeforeUnmount(() => {
  if (refreshHandle.value) clearInterval(refreshHandle.value);
});

// ----- Visual helpers -----------------------------------------------------

function statusColor(s: ComponentStatus): string {
  if (s === "ok") return "var(--signal-green)";
  if (s === "degraded") return "var(--signal-amber, #f59e0b)";
  return "var(--signal-red)";
}

function statusBg(s: ComponentStatus): string {
  if (s === "ok") return "var(--signal-green-bg)";
  if (s === "degraded") return "var(--signal-amber-bg, rgba(245,158,11,0.08))";
  return "var(--signal-red-bg)";
}

function statusGlyph(s: ComponentStatus): string {
  // Cockpit marks — geometric, not pictographic.
  if (s === "ok") return "●";
  if (s === "degraded") return "◐";
  return "○";
}

function statusLabel(s: ComponentStatus): string {
  if (s === "ok") return "All systems operational";
  if (s === "degraded") return "Partial degradation";
  return "Major outage";
}

const overall = computed<ComponentStatus | null>(() => data.value?.overall ?? null);

const lastUpdated = computed(() => {
  if (!data.value) return "—";
  const d = new Date(data.value.generated_at);
  return d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
});

const shortSha = computed(() => {
  const sha = data.value?.git_sha ?? "";
  return sha.length >= 7 ? sha.slice(0, 7) : sha;
});
</script>

<template>
  <div class="min-h-[calc(100vh-44px)] px-6 py-12">
    <div class="w-full max-w-[720px] mx-auto">
      <!-- Brand -->
      <div class="flex items-center justify-between mb-10">
        <div class="flex items-center gap-2 text-fg-subtle">
          <span class="text-signal-green font-mono text-section">◈</span>
          <span class="font-mono text-small tracking-[0.08em] uppercase">Vibecell · status</span>
        </div>
        <a
          href="/"
          class="font-mono text-small text-fg-subtle hover:text-fg-body transition-colors"
        >← back to vibecell.dev</a>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="mono-label opacity-50">probing components…</div>

      <!-- Error fetching status itself -->
      <div
        v-else-if="fetchError && !data"
        class="glass rounded-lg p-7"
        :style="{ borderColor: 'var(--signal-red)', borderWidth: '1px' }"
      >
        <MonoLabel>error</MonoLabel>
        <h1 class="text-display text-fg-primary tracking-tight mt-2">Status feed unreachable.</h1>
        <p class="text-body text-fg-muted mt-2">
          The /api/v1/status endpoint didn't respond. That can mean the API is fully down
          (in which case this page itself wouldn't load) — or your network can't reach it.
        </p>
        <p class="font-mono text-small text-fg-subtle mt-4">// {{ fetchError }}</p>
      </div>

      <template v-else-if="data && overall">
        <!-- Hero: overall verdict -->
        <section
          class="glass rounded-lg p-7 mb-6 flex items-center gap-5"
          :style="{
            background: statusBg(overall),
            borderColor: statusColor(overall),
            borderWidth: '1px',
          }"
        >
          <span
            class="font-mono text-[44px] leading-none shrink-0"
            :style="{ color: statusColor(overall) }"
            aria-hidden="true"
          >{{ statusGlyph(overall) }}</span>
          <div class="min-w-0 flex-1">
            <MonoLabel>{{ overall === "ok" ? "operational" : overall === "degraded" ? "degraded" : "down" }}</MonoLabel>
            <h1 class="text-display text-fg-primary tracking-tight mt-2">
              {{ statusLabel(overall) }}
            </h1>
            <p class="text-body text-fg-muted mt-1">
              Auto-refreshing every 30 seconds · last check
              <span class="font-mono">{{ lastUpdated }}</span>
            </p>
          </div>
        </section>

        <!-- Components table -->
        <section class="glass rounded-lg overflow-hidden mb-6">
          <header class="px-5 py-3 border-b border-border flex items-center justify-between">
            <MonoLabel>components</MonoLabel>
            <span class="font-mono text-small text-fg-subtle">{{ data.components.length }}</span>
          </header>
          <ul>
            <li
              v-for="(c, i) in data.components"
              :key="c.name"
              class="px-5 py-4 flex items-center gap-4"
              :style="{
                borderTop: i === 0 ? 'none' : '1px solid var(--border)',
              }"
            >
              <span
                class="w-2 h-2 rounded-full shrink-0"
                :style="{ background: statusColor(c.status), boxShadow: `0 0 12px ${statusColor(c.status)}` }"
                aria-hidden="true"
              />
              <div class="min-w-0 flex-1">
                <p class="text-body text-fg-primary font-medium">{{ c.name }}</p>
                <p
                  v-if="c.message"
                  class="text-small text-fg-muted mt-0.5 truncate"
                >{{ c.message }}</p>
              </div>
              <div class="text-right shrink-0">
                <p
                  class="font-mono text-small uppercase tracking-[0.06em]"
                  :style="{ color: statusColor(c.status) }"
                >{{ c.status }}</p>
                <p
                  v-if="c.latency_ms !== null"
                  class="font-mono text-[10px] text-fg-subtle mt-0.5"
                >{{ c.latency_ms }}ms</p>
              </div>
            </li>
          </ul>
        </section>

        <!-- Incident log (hidden when empty) -->
        <section
          v-if="data.incidents.length > 0"
          class="glass rounded-lg p-5 mb-6"
        >
          <MonoLabel class="mb-3">incidents · last 30 days</MonoLabel>
          <ul class="space-y-2">
            <li
              v-for="(inc, idx) in data.incidents"
              :key="idx"
              class="text-small text-fg-body"
            >
              {{ JSON.stringify(inc) }}
            </li>
          </ul>
        </section>

        <!-- Build footer -->
        <footer class="text-center font-mono text-[10px] text-fg-subtle">
          // build {{ shortSha }} · v{{ data.version }} · vibecell.dev
        </footer>
      </template>
    </div>
  </div>
</template>
