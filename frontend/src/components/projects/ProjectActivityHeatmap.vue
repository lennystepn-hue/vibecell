<script setup lang="ts">
/**
 * GitHub-contribution-style activity heatmap, 12 columns × 7 rows (≈12 weeks).
 * Monochrome — only shades of the app's signal-green; no rainbow.
 * Intensity per day = number of activity events that day.
 */
import { computed, ref, watch } from "vue";

import { onProjectLiveEvent } from "@/composables/useProjectLive";

const props = defineProps<{ slug: string }>();

interface ActivityEvent {
  type: string;
  at: string | null;
}

const events = ref<ActivityEvent[]>([]);

async function load(slug: string) {
  const r = await fetch(`/api/v1/projects/${slug}/activity?limit=500`, { credentials: "include" });
  if (r.ok && slug === props.slug) events.value = await r.json();
}

watch(() => props.slug, (s) => void load(s), { immediate: true });
onProjectLiveEvent("*", () => void load(props.slug));

const WEEKS = 12;  // ~ 3 months
const DAYS = WEEKS * 7;

// Grid indexed [col][row]; col 0 = oldest week on the left, row 0 = Monday top.
const grid = computed(() => {
  // Bucket events by local date YYYY-MM-DD
  const counts = new Map<string, number>();
  for (const e of events.value) {
    if (!e.at) continue;
    const d = new Date(e.at);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  // Build `DAYS` days ending today. Align so the rightmost column is "this week".
  const today = new Date();
  // Monday-start week: Mon=0..Sun=6
  const jsDay = today.getDay(); // 0=Sun..6=Sat
  const dayOfWeekMonStart = (jsDay + 6) % 7;
  // Step back to the start of the earliest week to keep the grid rectangular.
  const offset = (WEEKS - 1) * 7 + dayOfWeekMonStart;
  const start = new Date(today);
  start.setDate(today.getDate() - offset);

  const cells: { date: string; count: number; intensity: number; future: boolean }[][] = [];
  let maxCount = 0;
  for (let c = 0; c < WEEKS; c++) {
    const col: { date: string; count: number; intensity: number; future: boolean }[] = [];
    for (let r = 0; r < 7; r++) {
      const d = new Date(start);
      d.setDate(start.getDate() + c * 7 + r);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      const count = counts.get(key) ?? 0;
      if (count > maxCount) maxCount = count;
      col.push({
        date: key,
        count,
        intensity: 0,  // normalized below
        future: d > today,
      });
    }
    cells.push(col);
  }
  // Normalise intensity 0..4 (5 buckets = 5 shades) using a sqrt-compressed
  // scale so even one event reads clearly.
  for (const col of cells) {
    for (const cell of col) {
      if (cell.future || cell.count === 0) {
        cell.intensity = 0;
      } else if (maxCount <= 1) {
        cell.intensity = 3;
      } else {
        const scaled = Math.sqrt(cell.count) / Math.sqrt(maxCount);
        cell.intensity = Math.min(4, Math.max(1, Math.ceil(scaled * 4)));
      }
    }
  }
  return cells;
});

function cellClass(intensity: number, future: boolean) {
  if (future) return "opacity-0";
  // Monochrome ramp — just green alpha values (no hue shifts).
  const palette = [
    "bg-white/[0.035]",          // 0: nothing
    "bg-signal-green/20",        // 1
    "bg-signal-green/40",        // 2
    "bg-signal-green/60",        // 3
    "bg-signal-green/90",        // 4 — hottest
  ];
  return palette[intensity] ?? palette[0];
}

function label(cell: { date: string; count: number }): string {
  return `${cell.count} event${cell.count === 1 ? "" : "s"} · ${cell.date}`;
}

const total = computed(() => events.value.length);
</script>

<template>
  <section class="glass rounded-lg p-5">
    <header class="flex items-center justify-between mb-3">
      <h3 class="mono-label text-fg-muted">//activity-heatmap</h3>
      <span class="text-small text-fg-subtle font-mono tabular-nums">
        {{ total }} events · last 12 weeks
      </span>
    </header>

    <div class="flex gap-[3px]">
      <div
        v-for="(col, ci) in grid"
        :key="ci"
        class="flex flex-col gap-[3px]"
      >
        <div
          v-for="cell in col"
          :key="cell.date"
          class="w-[11px] h-[11px] rounded-sm transition-colors"
          :class="cellClass(cell.intensity, cell.future)"
          :title="label(cell)"
        />
      </div>
    </div>

    <!-- Legend -->
    <div class="flex items-center gap-1.5 mt-3 text-[10px] font-mono text-fg-subtle">
      <span>less</span>
      <span class="w-[11px] h-[11px] rounded-sm bg-white/[0.035]" />
      <span class="w-[11px] h-[11px] rounded-sm bg-signal-green/20" />
      <span class="w-[11px] h-[11px] rounded-sm bg-signal-green/40" />
      <span class="w-[11px] h-[11px] rounded-sm bg-signal-green/60" />
      <span class="w-[11px] h-[11px] rounded-sm bg-signal-green/90" />
      <span>more</span>
    </div>
  </section>
</template>
