<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import DataRow from "@/components/ui/DataRow.vue";
import MonoLabel from "@/components/ui/MonoLabel.vue";
import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

// ProjectFullOut backend model includes created_at + updated_at, but the
// generated OpenAPI types lag behind until `pnpm gen:api` runs against a
// deploy that exposes the new fields. Layer them in by hand so the
// telemetry rail can render the //METADATA rows without forcing a type
// regeneration step into every iteration.
type Project = components["schemas"]["ProjectFullOut"] & {
  created_at?: string | null;
  updated_at?: string | null;
};
type LifecycleEventOut = components["schemas"]["LifecycleEventOut"];

interface HealthEvent {
  probed_at: string;
  status: string;
  http_code: number | null;
  latency_ms: number | null;
}

interface HealthSummary {
  status?: string;
  message?: string;
  last_status?: string;
  last_probed_at?: string | null;
  uptime_24h_pct?: number | null;
  uptime_7d_pct?: number | null;
  avg_latency_ms_24h?: number | null;
  events_last_24h?: HealthEvent[];
  healthcheck_url?: string;
}

const props = defineProps<{ project: Project }>();

const events = ref<LifecycleEventOut[]>([]);
const health = ref<HealthSummary | null>(null);
const healthRefreshHandle = ref<ReturnType<typeof setInterval> | null>(null);

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toISOString().slice(0, 10);
}

function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

function kindIcon(kind: string): string {
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
  events.value = (data ?? [])
    .slice()
    .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
    .slice(0, 5);
}

// Health is served via a hand-shaped JSON payload by /api/v1/projects/{slug}/health.
// The endpoint always answers 200 — when nothing has been probed yet it
// returns {status: "not_probed_yet"|"not_configured"} so the rail can
// surface "add a healthcheck link" or "first probe within 5 minutes".
async function fetchHealth() {
  try {
    const res = await fetch(
      `/api/v1/projects/${props.project.slug}/health`,
      { credentials: "include" },
    );
    if (!res.ok) {
      health.value = null;
      return;
    }
    health.value = (await res.json()) as HealthSummary;
  } catch {
    health.value = null;
  }
}

onMounted(() => {
  void fetchEvents();
  void fetchHealth();
  // Re-probe every minute so the rail tracks new probe rows without a manual
  // refresh. Cron runs every 5 min, but the cheap re-fetch keeps "last
  // probed" labels honest in between.
  healthRefreshHandle.value = setInterval(fetchHealth, 60000);
});
watch(() => props.project.slug, () => {
  void fetchEvents();
  void fetchHealth();
});
onBeforeUnmount(() => {
  if (healthRefreshHandle.value) clearInterval(healthRefreshHandle.value);
});

// ---------- Derived health helpers --------------------------------------

const healthState = computed<"unconfigured" | "pending" | "healthy" | "down" | "unknown">(() => {
  if (!health.value) return "unknown";
  if (health.value.status === "not_configured") return "unconfigured";
  if (health.value.status === "not_probed_yet") return "pending";
  const last = health.value.last_status;
  if (last === "ok" || last === "healthy" || last === "up") return "healthy";
  if (last) return "down";
  return "unknown";
});

const uptime24h = computed<string>(() => {
  const v = health.value?.uptime_24h_pct;
  if (typeof v !== "number") return "—";
  return `${v.toFixed(1)}%`;
});

const ssl = computed<string>(() => {
  const url = health.value?.healthcheck_url
    ?? props.project.environments.find((e) => e.kind === "prod")?.url
    ?? null;
  if (!url) return "—";
  return url.startsWith("https://") ? "valid" : "—";
});

const issuesCount = computed<string>(() => {
  // Project-level "known issues" surface, harvested from project_context.known_issues.
  // It's the closest thing we have to an "open issues" counter without
  // wiring the GitHub issues API. Gives the rail a real number to display.
  const known = props.project.context?.known_issues;
  if (Array.isArray(known)) return String(known.length);
  return "0";
});

const healthBadge = computed<{ glyph: string; color: string } | null>(() => {
  switch (healthState.value) {
    case "healthy":
      return { glyph: "●", color: "var(--signal-green)" };
    case "down":
      return { glyph: "○", color: "var(--signal-red)" };
    case "pending":
      return { glyph: "◐", color: "var(--signal-amber, #f59e0b)" };
    case "unconfigured":
    case "unknown":
    default:
      return null;
  }
});

const lastProbed = computed<string>(() => {
  const iso = health.value?.last_probed_at;
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
});
</script>

<template>
  <aside class="chrome border-l w-[240px] shrink-0 flex flex-col h-full overflow-y-auto">
    <div class="p-4 space-y-5">
      <!-- ── //REPO ─────────────────────────────────────────────────── -->
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

      <!-- ── //ENVIRONMENTS ─────────────────────────────────────────── -->
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
                v-if="e.url && e.kind !== 'local'"
                :href="e.url"
                target="_blank"
                rel="noopener"
                class="link"
              >{{ hostOf(e.url) }}</a>
              <!-- 'local' URLs (localhost:5173 etc.) aren't external; render
                    as plain text so users don't try to click into nothing. -->
              <span v-else-if="e.url" class="font-mono text-fg-subtle">
                {{ hostOf(e.url) }}
              </span>
              <span v-else class="text-fg-subtle">—</span>
            </DataRow>
          </template>
          <p v-else class="text-small text-fg-muted italic">— none —</p>
        </div>
      </section>

      <!-- ── //METADATA ─────────────────────────────────────────────── -->
      <section>
        <MonoLabel>metadata</MonoLabel>
        <div class="mt-2 space-y-0.5">
          <DataRow label="created">
            <!-- created_at flows from ProjectOut after the API fix; previously
                 this row was bricked by an old `project.id ? null : null` test
                 that always evaluated to null. -->
            <span
              v-if="project.created_at"
              class="font-mono"
            >{{ formatDate(project.created_at) }}</span>
            <span v-else class="text-fg-subtle">—</span>
          </DataRow>
          <DataRow label="updated">
            <span
              v-if="project.updated_at"
              class="font-mono"
            >{{ formatDate(project.updated_at) }}</span>
            <span v-else class="text-fg-subtle">—</span>
          </DataRow>
          <DataRow v-if="project.archived_at" label="archived">
            <span class="font-mono">{{ formatDate(project.archived_at) }}</span>
          </DataRow>
          <DataRow label="status">
            <span class="font-mono uppercase tracking-[0.06em] text-[10px]">
              {{ project.status }}
            </span>
          </DataRow>
        </div>
      </section>

      <!-- ── //LIFECYCLE ────────────────────────────────────────────── -->
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

      <!-- ── //HEALTH ───────────────────────────────────────────────── -->
      <section>
        <MonoLabel>health</MonoLabel>

        <!-- Status pip — appears as soon as we have a real probe row -->
        <div v-if="healthBadge" class="mt-2 mb-2 flex items-center gap-2">
          <span
            class="font-mono text-section leading-none"
            :style="{ color: healthBadge.color }"
            aria-hidden="true"
          >{{ healthBadge.glyph }}</span>
          <span
            class="font-mono text-[10px] uppercase tracking-[0.06em]"
            :style="{ color: healthBadge.color }"
          >{{ healthState }}</span>
          <span class="font-mono text-[10px] text-fg-subtle ml-auto">
            {{ lastProbed }}
          </span>
        </div>

        <div class="space-y-0.5">
          <DataRow label="uptime">
            <span
              v-if="uptime24h !== '—'"
              class="font-mono"
            >{{ uptime24h }}</span>
            <span v-else class="text-fg-subtle">—</span>
          </DataRow>
          <DataRow label="ssl">
            <span
              v-if="ssl === 'valid'"
              class="font-mono"
              :style="{ color: 'var(--signal-green)' }"
            >valid</span>
            <span v-else class="text-fg-subtle">—</span>
          </DataRow>
          <DataRow label="known issues">
            <span
              class="font-mono"
              :style="issuesCount === '0'
                ? { color: 'var(--signal-green)' }
                : { color: 'var(--signal-amber, #f59e0b)' }"
            >{{ issuesCount }}</span>
          </DataRow>
        </div>

        <!-- Hint shown when nothing is wired up yet — actionable, not chrome -->
        <p
          v-if="healthState === 'unconfigured'"
          class="mono-label opacity-60 mt-2 text-[9px] leading-relaxed"
        >
          // add a healthcheck link<br>// to enable monitoring
        </p>
        <p
          v-else-if="healthState === 'pending'"
          class="mono-label opacity-60 mt-2 text-[9px] leading-relaxed"
        >
          // first probe within<br>// 5 minutes
        </p>
      </section>
    </div>
  </aside>
</template>
