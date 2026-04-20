<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import SidebarProjects from "@/components/app/SidebarProjects.vue";
import MonoLabel from "@/components/ui/MonoLabel.vue";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ActivityCell {
  project_id: string;
  week: string;    // e.g. "2026-W15"
  event_count: number;
}

interface StagnantProject {
  project_id: string;
  slug: string;
  name: string;
  days_since_activity: number;
  last_activity_at: string | null;
}

interface PortfolioSnapshot {
  workspace_id: string;
  generated_at: string;
  project_count: number;
  active_project_count: number;
  stagnant_projects: StagnantProject[];
  activity_by_week: ActivityCell[];
  recommendations: unknown[];
  dependency_alerts: unknown[];
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

const snapshot = ref<PortfolioSnapshot | null>(null);
const loading = ref(true);
const loadError = ref<string | null>(null);

onMounted(async () => {
  try {
    const res = await fetch("/api/v1/portfolio/snapshot", {
      credentials: "include",
    });
    if (res.ok) {
      snapshot.value = await res.json();
    } else if (res.status === 501) {
      loadError.value = "Portfolio snapshot not yet implemented. Run Spec 5B.1 to enable.";
    } else {
      loadError.value = `Error ${res.status}`;
    }
  } catch {
    loadError.value = "Failed to load portfolio data";
  } finally {
    loading.value = false;
  }
});

// ---------------------------------------------------------------------------
// Heatmap computation
// ---------------------------------------------------------------------------

const HEATMAP_WEEKS = 12;

/** Generate a sorted list of ISO week strings for the last N weeks. */
function lastNWeeks(n: number): string[] {
  const weeks: string[] = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i * 7);
    // ISO week: YYYY-Www
    const jan4 = new Date(d.getFullYear(), 0, 4);
    const dayOfYear = Math.floor((d.getTime() - new Date(d.getFullYear(), 0, 0).getTime()) / 86400000);
    const week = Math.ceil((dayOfYear + jan4.getDay() - 1) / 7);
    weeks.push(`${d.getFullYear()}-W${String(week).padStart(2, "0")}`);
  }
  return weeks;
}

const weeks = computed(() => lastNWeeks(HEATMAP_WEEKS));

/** Get unique project IDs from activity data (preserving order). */
const heatmapProjectIds = computed((): string[] => {
  if (!snapshot.value) return [];
  const seen = new Set<string>();
  const order: string[] = [];
  // Sort by most recently active
  const byProject = new Map<string, number>();
  for (const cell of snapshot.value.activity_by_week) {
    byProject.set(cell.project_id, (byProject.get(cell.project_id) ?? 0) + cell.event_count);
  }
  const sorted = [...byProject.entries()].sort((a, b) => b[1] - a[1]);
  for (const [pid] of sorted) {
    if (!seen.has(pid)) { seen.add(pid); order.push(pid); }
  }
  return order;
});

/** Lookup map: project_id+week → event_count */
const activityMap = computed(() => {
  const m = new Map<string, number>();
  if (!snapshot.value) return m;
  for (const cell of snapshot.value.activity_by_week) {
    m.set(`${cell.project_id}:${cell.week}`, cell.event_count);
  }
  return m;
});

function cellCount(projectId: string, week: string): number {
  return activityMap.value.get(`${projectId}:${week}`) ?? 0;
}

function cellColor(count: number): string {
  if (count === 0) return "var(--bg-elevated)";
  if (count <= 1) return "rgba(74, 222, 128, 0.25)";
  if (count <= 3) return "rgba(74, 222, 128, 0.50)";
  if (count <= 6) return "rgba(74, 222, 128, 0.75)";
  return "var(--signal-green)";
}

function shortWeek(week: string): string {
  // "2026-W15" → "W15"
  return week.split("-")[1] ?? week;
}

/** Get project name from snapshot data (fallback to slug). */
function projectLabel(pid: string): string {
  // We only have data from the activity cells — no name in heatmap data
  // Use stagnant projects data as well to resolve names
  if (!snapshot.value) return pid.slice(0, 8);
  const sp = snapshot.value.stagnant_projects.find(p => p.project_id === pid);
  return sp?.name ?? sp?.slug ?? pid.slice(0, 8);
}
</script>

<template>
  <div class="flex h-[calc(100vh-44px)]">
    <SidebarProjects />

    <main class="flex-1 min-w-0 overflow-y-auto">
      <div class="max-w-[1100px] px-8 py-8 mx-auto">
        <!-- Header -->
        <header class="mb-8">
          <h1 class="text-display text-fg-primary mb-2">Portfolio</h1>
          <p class="text-body text-fg-muted">Cross-project intelligence — activity, stagnation, and signals.</p>
        </header>

        <!-- Loading -->
        <div v-if="loading" class="text-small text-fg-subtle font-mono">Generating snapshot…</div>

        <!-- Error / Not implemented -->
        <div
          v-else-if="loadError"
          class="glass rounded-lg p-6"
          :style="{ background: 'var(--signal-amber-bg, rgba(245,158,11,0.08))', border: '1px solid rgba(245,158,11,0.3)' }"
        >
          <p class="text-section text-fg-primary mb-1">Portfolio Intel — Coming in Spec 5B.1</p>
          <p class="text-small text-fg-muted">{{ loadError }}</p>
        </div>

        <template v-else-if="snapshot">
          <!-- Stats row -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div class="glass rounded-lg p-4">
              <p class="mono-label mb-1">projects</p>
              <p class="text-title text-fg-primary font-mono">{{ snapshot.project_count }}</p>
            </div>
            <div class="glass rounded-lg p-4">
              <p class="mono-label mb-1">active</p>
              <p class="text-title text-fg-primary font-mono">{{ snapshot.active_project_count }}</p>
            </div>
            <div class="glass rounded-lg p-4">
              <p class="mono-label mb-1">stagnant</p>
              <p
                class="text-title font-mono"
                :style="{ color: snapshot.stagnant_projects.length > 0 ? 'var(--signal-amber, #f59e0b)' : 'var(--signal-green)' }"
              >
                {{ snapshot.stagnant_projects.length }}
              </p>
            </div>
            <div class="glass rounded-lg p-4">
              <p class="mono-label mb-1">updated</p>
              <p class="text-small text-fg-muted font-mono">
                {{ new Date(snapshot.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }}
              </p>
            </div>
          </div>

          <!-- Stagnation warnings -->
          <div v-if="snapshot.stagnant_projects.length > 0" class="mb-8">
            <MonoLabel class="mb-3">needs attention</MonoLabel>
            <div class="space-y-2">
              <div
                v-for="sp in snapshot.stagnant_projects"
                :key="sp.project_id"
                class="flex items-center gap-4 glass rounded-lg px-4 py-3"
                :style="{ borderLeft: '3px solid var(--signal-amber, #f59e0b)' }"
              >
                <div class="flex-1 min-w-0">
                  <p class="text-small text-fg-primary font-medium">{{ sp.name }}</p>
                  <p class="text-small text-fg-muted font-mono">{{ sp.slug }}</p>
                </div>
                <div class="text-right">
                  <p class="text-small font-mono" :style="{ color: 'var(--signal-amber, #f59e0b)' }">
                    {{ sp.days_since_activity === 9999 ? "never active" : `${sp.days_since_activity}d quiet` }}
                  </p>
                  <p v-if="sp.last_activity_at" class="text-small text-fg-subtle">
                    last: {{ new Date(sp.last_activity_at).toLocaleDateString() }}
                  </p>
                </div>
                <router-link
                  :to="`/p/${sp.slug}`"
                  class="text-small text-fg-subtle hover:text-fg-body transition-colors"
                >
                  →
                </router-link>
              </div>
            </div>
          </div>

          <!-- Activity heatmap -->
          <div v-if="snapshot.activity_by_week.length > 0">
            <MonoLabel class="mb-3">activity heatmap · last {{ weeks.length }} weeks</MonoLabel>

            <div class="glass rounded-lg p-4 overflow-x-auto">
              <!-- Week labels header -->
              <div
                class="grid gap-1 mb-2"
                :style="{ gridTemplateColumns: `120px repeat(${weeks.length}, 1fr)` }"
              >
                <div />
                <div
                  v-for="w in weeks"
                  :key="w"
                  class="text-center font-mono text-[10px] text-fg-subtle"
                >
                  {{ shortWeek(w) }}
                </div>
              </div>

              <!-- Project rows -->
              <div
                v-for="pid in heatmapProjectIds"
                :key="pid"
                class="grid gap-1 mb-1 items-center"
                :style="{ gridTemplateColumns: `120px repeat(${weeks.length}, 1fr)` }"
              >
                <!-- Project name -->
                <router-link
                  :to="`/p/${pid}`"
                  class="text-small text-fg-muted hover:text-fg-body transition-colors truncate pr-2 font-mono text-[11px]"
                  :title="projectLabel(pid)"
                >
                  {{ projectLabel(pid) }}
                </router-link>

                <!-- Week cells -->
                <div
                  v-for="w in weeks"
                  :key="w"
                  class="aspect-square rounded-sm transition-colors cursor-default"
                  :style="{ background: cellColor(cellCount(pid, w)) }"
                  :title="`${projectLabel(pid)} · ${w} · ${cellCount(pid, w)} events`"
                />
              </div>
            </div>

            <!-- Legend -->
            <div class="flex items-center gap-2 mt-3">
              <span class="text-small text-fg-subtle font-mono">less</span>
              <div
                v-for="count in [0, 1, 3, 5, 7]"
                :key="count"
                class="w-4 h-4 rounded-sm"
                :style="{ background: cellColor(count) }"
              />
              <span class="text-small text-fg-subtle font-mono">more</span>
            </div>
          </div>

          <!-- No data state -->
          <div v-else class="glass rounded-lg p-8 text-center">
            <p class="text-section text-fg-primary mb-2">No activity data yet</p>
            <p class="text-small text-fg-muted">
              Activity appears here once you start shipping, logging sessions, and making decisions.
            </p>
          </div>
        </template>
      </div>
    </main>
  </div>
</template>
