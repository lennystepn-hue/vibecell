<script setup lang="ts">
import { computed, ref, watch } from "vue";

const props = defineProps<{ slug: string }>();

interface Stats {
  last_session_at: string | null;
  session_count_7d: number;
  decision_count_total: number;
  secrets_count: number;
  commits_7d: number;
}

const stats = ref<Stats | null>(null);

async function load(slug: string) {
  stats.value = null;
  try {
    // Pulled from the activity feed (cheap single call) plus secrets list for
    // secret count. Keep this component's data footprint small — it's a
    // chip row, not a dashboard.
    const [actRes, secRes] = await Promise.all([
      fetch(`/api/v1/projects/${slug}/activity?limit=200`, { credentials: "include" }),
      fetch(`/api/v1/projects/${slug}/secrets`, { credentials: "include" }),
    ]);
    const events = actRes.ok ? await actRes.json() as Array<any> : [];
    const secrets = secRes.ok ? await secRes.json() as Array<any> : [];
    if (slug !== props.slug) return;  // stale navigation response

    const now = Date.now();
    const sevenDays = 7 * 24 * 60 * 60 * 1000;
    const sessions = events.filter((e) => e.type === "session");
    const decisions = events.filter((e) => e.type === "decision");
    const sessions7d = sessions.filter((e) => e.at && now - new Date(e.at).getTime() < sevenDays);
    const commits7d = sessions7d.reduce(
      (acc, s) => acc + (s.meta?.commit_count ?? 0),
      0,
    );

    stats.value = {
      last_session_at: sessions[0]?.at ?? null,
      session_count_7d: sessions7d.length,
      decision_count_total: decisions.length,
      secrets_count: secrets.length,
      commits_7d: commits7d,
    };
  } catch {
    /* noop — chip row is best-effort */
  }
}

watch(() => props.slug, (slug) => void load(slug), { immediate: true });

function relative(iso: string | null): string {
  if (!iso) return "never";
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return "just now";
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
  return `${Math.floor(ms / 86_400_000)}d ago`;
}

const hasAny = computed(() => stats.value !== null);
</script>

<template>
  <div
    v-if="hasAny"
    class="flex flex-wrap gap-2 text-small text-fg-muted"
  >
    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border bg-bg-surface/40">
      <span class="w-1 h-1 rounded-full bg-signal-green" />
      <span class="mono-label">last session</span>
      <span class="text-fg-body">{{ relative(stats?.last_session_at ?? null) }}</span>
    </span>
    <span
      v-if="stats && stats.session_count_7d > 0"
      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border bg-bg-surface/40"
    >
      <span class="mono-label">7d</span>
      <span class="tabular-nums text-fg-body">{{ stats.session_count_7d }}</span>
      <span>sessions</span>
    </span>
    <span
      v-if="stats && stats.commits_7d > 0"
      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border bg-bg-surface/40"
    >
      <span class="mono-label">7d</span>
      <span class="tabular-nums text-fg-body">{{ stats.commits_7d }}</span>
      <span>commits</span>
    </span>
    <span
      v-if="stats && stats.decision_count_total > 0"
      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border bg-bg-surface/40"
    >
      <span class="tabular-nums text-fg-body">{{ stats.decision_count_total }}</span>
      <span>decisions</span>
    </span>
    <span
      v-if="stats && stats.secrets_count > 0"
      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border bg-bg-surface/40"
    >
      <span class="tabular-nums text-fg-body">{{ stats.secrets_count }}</span>
      <span>secrets</span>
    </span>
  </div>
</template>
